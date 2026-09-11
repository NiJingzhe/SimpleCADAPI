"""SolidWorks runtime fragment: DocumentMetadataMixin."""


class DocumentMetadataMixin:
    def _set_document_custom_property(self, manager, name, value):
        errors = []
        for call in (
            lambda: manager.Add3(str(name), 30, str(value), 2),
            lambda: manager.Set2(str(name), str(value)),
        ):
            try:
                call()
                return
            except Exception as exc:
                errors.append(str(exc))
        raise RuntimeError(
            f'could not write custom property {name!r}: {errors!r}'
        )

    def _document_custom_property_value(self, manager, name):
        try:
            return str(_maybe_call(manager.Get(str(name))) or '')
        except Exception as exc:
            raise RuntimeError(
                f'could not read custom property {name!r}: {exc}'
            ) from exc

    def _persist_chunked_json_property(
        self, manager, prefix, payload, schema
    ):
        raw = json.dumps(
            payload,
            ensure_ascii=True,
            separators=(',', ':'),
            sort_keys=True,
        ).encode('ascii')
        encoded = base64.b64encode(
            zlib.compress(raw, level=9)
        ).decode('ascii')
        chunk_size = 900
        chunks = [
            encoded[index:index + chunk_size]
            for index in range(0, len(encoded), chunk_size)
        ] or ['']
        metadata = json.dumps(
            {
                'schema': str(schema),
                'chunks': len(chunks),
                'sha256': hashlib.sha256(raw).hexdigest(),
            },
            ensure_ascii=True,
            separators=(',', ':'),
            sort_keys=True,
        )
        for index, chunk in enumerate(chunks):
            self._set_document_custom_property(
                manager, f'{prefix}.{index:04d}', chunk
            )
        self._set_document_custom_property(
            manager, f'{prefix}.Meta', metadata
        )

        persisted_meta = json.loads(
            self._document_custom_property_value(
                manager, f'{prefix}.Meta'
            )
        )
        persisted_encoded = ''.join(
            self._document_custom_property_value(
                manager, f'{prefix}.{index:04d}'
            )
            for index in range(int(persisted_meta.get('chunks', 0)))
        )
        persisted_raw = zlib.decompress(
            base64.b64decode(persisted_encoded.encode('ascii'))
        )
        if (
            persisted_meta.get('schema') != str(schema)
            or persisted_meta.get('sha256')
            != hashlib.sha256(persisted_raw).hexdigest()
            or persisted_raw != raw
        ):
            raise RuntimeError(
                f'custom property readback mismatch for {prefix!r}'
            )
        return len(chunks)

    def _persist_topology_maps(self, manager):
        chunk_size = 900
        for source_node_id in sorted(self.persisted_topology_maps):
            payload = self.persisted_topology_maps[source_node_id]
            raw = json.dumps(
                payload,
                ensure_ascii=True,
                separators=(',', ':'),
                sort_keys=True,
            ).encode('ascii')
            encoded = base64.b64encode(
                zlib.compress(raw, level=9)
            ).decode('ascii')
            chunks = [
                encoded[index:index + chunk_size]
                for index in range(0, len(encoded), chunk_size)
            ] or ['']
            prefix = f'SimpleCADTopo.{source_node_id}'
            try:
                for index, chunk in enumerate(chunks):
                    self._set_document_custom_property(
                        manager,
                        f'{prefix}.{index:04d}',
                        chunk,
                    )
                metadata = json.dumps(
                    {
                        'schema': 'simplecad-sw-topology-v1',
                        'method': 'gsm',
                        'chunks': len(chunks),
                        'sha256': hashlib.sha256(raw).hexdigest(),
                    },
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                # Meta is written last so a partial chunk set is never valid.
                self._set_document_custom_property(
                    manager, f'{prefix}.Meta', metadata
                )
                self.logs.append(
                    f'persisted GSM topology properties for {source_node_id}: '
                    f'entries={len(payload.get("mappings") or {})} '
                    f'chunks={len(chunks)}'
                )
            except Exception as exc:
                self.logs.append(
                    f'could not persist GSM topology map for '
                    f'{source_node_id}: {exc}'
                )

    def _persist_document_metadata(self):
        try:
            manager = self.model.Extension.CustomPropertyManager('')
            if self.degraded_features:
                payload = json.dumps(
                    self.degraded_features,
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                for call in (
                    lambda: manager.Add3(
                        'SimpleCADDegradedFeatures', 30, payload, 2
                    ),
                    lambda: manager.Set2(
                        'SimpleCADDegradedFeatures', payload
                    ),
                ):
                    try:
                        call()
                        break
                    except Exception:
                        pass
            self._persist_topology_maps(manager)
            native_ops = {
                'make_extrude_rsolid', 'make_revolve_rsolid',
                'make_cut_rsolid', 'make_union_rsolid',
                'make_intersect_rsolid', 'make_fillet_rsolid',
                'make_chamfer_rsolid', 'make_shell_rsolid',
                'make_translate_rshape', 'make_rotate_rshape',
                'make_mirror_rshape',
            }
            for node in self.nodes:
                op = str(node.get('op') or '')
                if op not in native_ops:
                    continue
                node_id = str(node.get('node_id') or '')
                body_names = []
                for output in self.outputs.get(node_id) or []:
                    if not isinstance(output, dict):
                        continue
                    if output.get('kind') == 'body':
                        output_names = [output.get('_body_name')]
                    elif output.get('kind') == 'compound':
                        output_names = output.get('_body_names') or []
                    else:
                        output_names = []
                    for body_name in output_names:
                        body_name = str(body_name or '')
                        if body_name and body_name not in body_names:
                            body_names.append(body_name)
                value = json.dumps(
                    {
                        'NodeId': node_id,
                        'Op': op,
                        'Params': node.get('params') or {},
                        'Inputs': self._input_ids(node),
                        'BodyNames': body_names,
                        'FeatureNamePrefix': f'SimpleCAD_{node_id}_',
                    },
                    ensure_ascii=True,
                    separators=(',', ':'),
                    sort_keys=True,
                )
                try:
                    manager.Add3(
                        f'SimpleCADNode.{node_id}', 30, value, 2
                    )
                except Exception as exc:
                    self.logs.append(
                        f'could not persist node metadata for {node_id}: {exc}'
                    )
        except Exception as exc:
            self.logs.append(f'could not persist degraded feature metadata: {exc}')

    def _persistent_reference_bytes(self, entity):
        def coerce(value):
            if value is None:
                return None
            if isinstance(value, bytes):
                return value
            if isinstance(value, bytearray):
                return bytes(value)
            if isinstance(value, memoryview):
                return value.tobytes()
            if hasattr(value, 'value'):
                nested = coerce(value.value)
                if nested:
                    return nested
            if isinstance(value, (list, tuple)):
                if value and all(
                    isinstance(item, int) and 0 <= item <= 255
                    for item in value
                ):
                    return bytes(value)
                for item in value:
                    nested = coerce(item)
                    if nested:
                        return nested
            return None

        extension = self.model.Extension
        for call in (
            lambda: extension.GetPersistReference3(entity),
            lambda: extension.GetPersistReference(entity),
        ):
            try:
                reference = coerce(call())
                if reference:
                    return reference
            except Exception:
                pass
        return None

    def _resolve_persistent_reference_bytes(self, reference):
        if not reference:
            return None
        try:
            value = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_UI1,
                tuple(bytes(reference)),
            )
            error = win32com.client.VARIANT(
                pythoncom.VT_BYREF | pythoncom.VT_I4, 0
            )
            entity = self.model.Extension.GetObjectByPersistReference3(
                value, error
            )
            if entity is not None and int(error.value) == 0:
                return entity
        except Exception:
            pass
        return None


__all__ = ["DocumentMetadataMixin"]
