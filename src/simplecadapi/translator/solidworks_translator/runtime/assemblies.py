"""SolidWorks runtime fragment: AssemblyRuntimeMixin."""


class AssemblyRuntimeMixin:
    def _assembly_with_placements(self, assembly, placements):
        value = dict(assembly)
        known = {str(c.get('component_id')) for c in assembly.get('components', [])}
        if set(placements) - known:
            raise RuntimeError('Solved placement references a missing component')
        components = []
        for source in assembly.get('components', []):
            component = dict(source)
            component_id = str(component.get('component_id'))
            if component_id in placements:
                component['placement'] = {
                    'kind': 'placement', 'params': dict(placements[component_id]),
                }
            components.append(component)
        value['components'] = components
        return value

    def _assembly_with_public_connector(self, assembly, params):
        public_id = str(params.get('public_connector_id') or '')
        component_id = str(params.get('source_component_id') or '')
        connector_id = str(params.get('source_connector_id') or '')
        if not all((public_id, component_id, connector_id)):
            raise RuntimeError('Public connector requires non-empty IDs')
        public = list(assembly.get('public_connectors') or [])
        if any(c['public_connector_id'] == public_id for c in public):
            raise RuntimeError(f'duplicate public_connector_id in assembly: {public_id}')
        component = next((c for c in assembly.get('components', [])
                          if str(c.get('component_id')) == component_id), None)
        if component is None:
            raise RuntimeError(f'Public connector references missing component: {component_id}')
        item = component['item']
        if item.get('kind') == 'assembly':
            connector_ids = {c['public_connector_id'] for c in item.get('public_connectors', [])}
        else:
            connector_ids = {c['params']['connector_id'] for c in item.get('connectors', [])}
        if connector_id not in connector_ids:
            raise RuntimeError(f'Public connector references missing connector: {connector_id}')
        public.append({
            'public_connector_id': public_id, 'name': params.get('name'),
            'component_id': component_id, 'connector_id': connector_id,
        })
        value = dict(assembly)
        value['public_connectors'] = public
        return value

    def _save_native_assembly(self, step_path, assembly_path):
        master_model = self.model
        master_title = str(_maybe_call(master_model.GetTitle))
        assembly_path = os.path.abspath(assembly_path)
        assembly_directory = os.path.dirname(assembly_path)
        component_directory = os.path.join(
            assembly_directory,
            os.path.splitext(os.path.basename(assembly_path))[0]
            + '_components',
        )
        os.makedirs(component_directory, exist_ok=True)
        master_part_path = _native_part_output_path(step_path)
        package_master_path = os.path.join(
            component_directory, '_SimpleCADMaster.sldprt'
        )
        shutil.copy2(master_part_path, package_master_path)
        component_records = []
        prepared_occurrences = []
        self.model = master_model
        for occurrence in self.assembly_occurrences:
            prepared_occurrences.append((
                occurrence,
                occurrence.get('prepared_source_body')
                or self._copy_temp_body(
                    occurrence.get('source_body') or occurrence.get('body')
                ),
            ))

        for index, (occurrence, temp_body) in enumerate(prepared_occurrences):
            component_id = str(
                occurrence.get('component_id') or f'component_{index + 1}'
            )
            source_node_id = str(
                occurrence.get('source_node_id') or ''
            )
            token = ''.join(
                character if character.isalnum() or character in '._-'
                else '_'
                for character in component_id
            ) or f'component_{index + 1}'
            if any(record['component_id'] == component_id for record in component_records):
                token += f'_{index + 1}'
            component_path = os.path.join(
                component_directory, token + '.sldprt'
            )
            component_model = self._new_part()
            feature = None
            derived_component = False
            self.model = component_model
            try:
                try:
                    part_doc = win32com.client.CastTo(
                        component_model, 'IPartDoc'
                    )
                except Exception:
                    part_doc = component_model
                derived_feature = None
                for api_name, call in (
                    (
                        'InsertPart3',
                        lambda: part_doc.InsertPart3(
                            package_master_path, 1, ''
                        ),
                    ),
                    (
                        'InsertPart2',
                        lambda: part_doc.InsertPart2(
                            package_master_path, 1
                        ),
                    ),
                    (
                        'InsertPart',
                        lambda: part_doc.InsertPart(
                            package_master_path, False, False, False
                        ),
                    ),
                ):
                    try:
                        derived_feature = call()
                        if derived_feature is not None:
                            self.logs.append(
                                f'{component_id} derived part uses '
                                f'{api_name}'
                            )
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'{component_id} {api_name} failed: {exc}'
                        )
                if derived_feature is not None:
                    derived_feature.Name = (
                        f'SimpleCADDerived_{token}'
                    )
                    component_model.ForceRebuild3(False)
                    candidates = self._solid_bodies()
                    expected_bbox = occurrence.get('source_expected_bbox')
                    if not candidates or not isinstance(expected_bbox, dict):
                        raise RuntimeError(
                            'derived component has no selectable result bodies'
                        )
                    source_node_id = str(
                        occurrence.get('source_node_id') or ''
                    )
                    source_body_name = str(
                        occurrence.get('source_body_name') or ''
                    )
                    source_owner = str(
                        occurrence.get('source_owner') or ''
                    )

                    def candidate_labels(candidate):
                        labels = [self._body_name(candidate)]
                        for getter_name in ('GetFeature', 'IGetFeature'):
                            try:
                                owner = _maybe_call(
                                    getattr(candidate, getter_name)
                                )
                                owner_name = str(
                                    _maybe_call(owner.Name) if owner else ''
                                )
                                if owner_name:
                                    labels.append(owner_name)
                                    break
                            except Exception:
                                pass
                        return labels

                    exact_candidates = []
                    node_candidates = []
                    for candidate in candidates:
                        labels = candidate_labels(candidate)
                        if any(
                            expected and expected in labels
                            for expected in (source_body_name, source_owner)
                        ):
                            exact_candidates.append(candidate)
                        elif source_node_id and any(
                            source_node_id in label for label in labels
                        ):
                            node_candidates.append(candidate)
                    preferred = exact_candidates or node_candidates or candidates
                    ranked = sorted(
                        [
                            [
                                _bbox_score(
                                    self._box_from_entity(candidate),
                                    expected_bbox,
                                ),
                                candidate,
                            ]
                            for candidate in preferred
                        ],
                        key=lambda item: item[0],
                    )
                    best_score, selected_body = ranked[0]
                    expected_size = _distance(
                        expected_bbox.get('min'), expected_bbox.get('max')
                    )
                    match_tolerance = max(
                        1.0e-7, expected_size * 1.0e-6
                    )
                    matching = [
                        candidate for score, candidate in ranked
                        if score <= match_tolerance
                    ]
                    if best_score > match_tolerance:
                        raise RuntimeError(
                            f'derived component body mismatch: {best_score}'
                        )
                    if len(matching) != 1:
                        raise RuntimeError(
                            f'derived component body match is ambiguous: '
                            f'{len(matching)} candidates'
                        )
                    if len(candidates) > 1:
                        self._clear_selection()
                        if not self._select_entity(selected_body):
                            raise RuntimeError(
                                'could not select derived component body'
                            )
                        keep_feature = (
                            component_model.FeatureManager.InsertDeleteBody2(
                                True
                            )
                        )
                        self._clear_selection()
                        if keep_feature is None:
                            raise RuntimeError(
                                'could not keep derived component body'
                            )
                        keep_feature.Name = (
                            f'SimpleCADKeep_{token}'
                        )
                        feature = keep_feature
                    else:
                        feature = derived_feature
                    component_model.ForceRebuild3(False)
                    if len(self._solid_bodies()) != 1:
                        raise RuntimeError(
                            'derived component did not resolve to one body'
                        )
                    if MODEL_SCALE > 1.0 + 1.0e-12:
                        scaled_body = self._solid_bodies()[0]
                        self._clear_selection()
                        if not self._select_solid_body(
                            scaled_body, append=False, mark=1
                        ):
                            raise RuntimeError(
                                'could not select derived component for scale'
                            )
                        factor = 1.0 / MODEL_SCALE
                        scale_feature = (
                            component_model.FeatureManager.InsertScale(
                                1, True, factor, factor, factor
                            )
                        )
                        self._clear_selection()
                        if scale_feature is None:
                            raise RuntimeError(
                                'could not restore derived component scale'
                            )
                        scale_feature.Name = (
                            f'SimpleCADScale_{token}'
                        )
                        feature = scale_feature
                        component_model.ForceRebuild3(False)
                        if len(self._solid_bodies()) != 1:
                            raise RuntimeError(
                                'scaled derived component did not resolve '
                                'to one body'
                            )
                    derived_component = True
            except Exception as exc:
                self.logs.append(
                    f'live derived component failed for {component_id}: '
                    f'{exc}'
                )
            finally:
                self.model = master_model
            if not derived_component:
                component_title = str(_maybe_call(component_model.GetTitle))
                self.sw.CloseDoc(component_title)
                component_model = self._new_part()
                feature = None
                if MODEL_SCALE > 1.0 + 1.0e-12:
                    scale_matrix = _identity_matrix()
                    scale_matrix[12] = 1.0 / MODEL_SCALE
                    self._apply_transform_to_temp_body(
                        temp_body, scale_matrix
                    )
                self._mark_degraded(
                    f'SimpleCADComponent_{token}',
                    'static_component_body',
                )
                for call in (
                    lambda: component_model.CreateFeatureFromBody3(
                        temp_body, False, 0
                    ),
                    lambda: component_model.CreateFeatureFromBody2(
                        temp_body, False, 0
                    ),
                    lambda: component_model.CreateFeatureFromBody(temp_body),
                ):
                    try:
                        feature = call()
                        if feature is not None:
                            break
                    except Exception:
                        pass
            if feature is None:
                raise RuntimeError(
                    f'Could not materialize component part for {component_id}'
                )
            try:
                feature.Name = f'SimpleCADComponent_{token}'
            except Exception:
                pass
            properties = component_model.Extension.CustomPropertyManager('')
            component_properties = {
                'SimpleCADComponentId': component_id,
                'SimpleCADSourceNodeId': source_node_id,
                'SimpleCADDegradedStaticComponent': (
                    'false' if derived_component else 'true'
                ),
                'SimpleCADMasterPartPath': package_master_path,
            }
            for property_name, property_value in component_properties.items():
                self._set_document_custom_property(
                    properties, property_name, property_value
                )
                if self._document_custom_property_value(
                    properties, property_name
                ) != str(property_value):
                    raise RuntimeError(
                        f'component property readback mismatch for '
                        f'{component_id}:{property_name}'
                    )
            dependency_node_ids = list(
                occurrence.get('dependency_node_ids') or []
            )
            self._persist_chunked_json_property(
                properties,
                'SimpleCADDependencies',
                {
                    'component_id': component_id,
                    'source_node_id': source_node_id,
                    'dependency_node_ids': dependency_node_ids,
                },
                'simplecad-sw-component-dependencies-v1',
            )
            errors = _byref_i4()
            warnings = _byref_i4()
            ok = component_model.Extension.SaveAs(
                component_path,
                SW_SAVE_AS_CURRENT_VERSION,
                SW_SAVE_AS_OPTIONS_SILENT,
                _empty_dispatch(),
                errors,
                warnings,
            )
            if not ok or not os.path.exists(component_path):
                raise RuntimeError(
                    f'Could not save component part for {component_id}; '
                    f'errors={errors.value} warnings={warnings.value}'
                )
            component_title = str(_maybe_call(component_model.GetTitle))
            self.sw.CloseDoc(component_title)
            self._activate_document(master_title)
            component_records.append({
                'component_id': component_id,
                'path': component_path,
                'graph_path': list(occurrence.get('path') or ()),
                'derived_component': derived_component,
                'source_node_id': source_node_id,
                'dependency_node_ids': dependency_node_ids,
                'transform': _assembly_component_matrix(
                    occurrence.get('placements') or ()
                ),
            })
            print(
                f'SIMPLECAD_SW_ASSEMBLY_PARTS={index + 1}/'
                f'{len(prepared_occurrences)}:{component_id}',
                flush=True,
            )

        assembly_model = self._new_document('assembly')
        try:
            assembly_doc = win32com.client.CastTo(
                assembly_model, 'IAssemblyDoc'
            )
        except Exception:
            assembly_doc = assembly_model
        assembly_title = str(_maybe_call(assembly_model.GetTitle))
        inserted = []
        for insertion_index, record in enumerate(component_records):
            component_model, open_errors, open_warnings = self._open_document(
                record['path'], SW_DOC_PART
            )
            if component_model is None or open_errors != 0:
                raise RuntimeError(
                    f"Could not load assembly component "
                    f"{record['component_id']}; errors={open_errors} "
                    f"warnings={open_warnings}"
                )
            self._activate_document(assembly_title)
            component = assembly_doc.AddComponent5(
                record['path'], 0, '', False, '', 0.0, 0.0, 0.0
            )
            if component is None:
                raise RuntimeError(
                    f"Could not insert assembly component "
                    f"{record['component_id']}"
                )
            # AddComponent5 requires the part to be loaded first, but the
            # assembly owns that loaded reference after insertion. Keeping
            # every OpenDoc6 result open as a top-level document exhausts the
            # COM server on large assemblies (069 has 60 unique parts).
            component_title = str(_maybe_call(component_model.GetTitle))
            try:
                self.sw.CloseDoc(component_title)
            except Exception as exc:
                self.logs.append(
                    f"could not close inserted component document "
                    f"{record['component_id']}: {exc}"
                )
            component_model = None
            graph_path_json = json.dumps(
                record.get('graph_path') or [],
                ensure_ascii=True,
                separators=(',', ':'),
            )
            graph_path_digest = hashlib.sha256(
                graph_path_json.encode('ascii')
            ).hexdigest()[:16]
            expected_reference = (
                f"{record['component_id']}|"
                f"{record.get('source_node_id') or ''}|"
                f"{graph_path_digest}"
            )
            try:
                component.ComponentReference = expected_reference
                actual_reference = str(
                    _maybe_call(component.ComponentReference) or ''
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Could not persist component reference for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if actual_reference != expected_reference:
                raise RuntimeError(
                    f"Component reference readback mismatch for "
                    f"{record['component_id']}: expected="
                    f"{expected_reference!r} actual={actual_reference!r}"
                )
            record['component_reference'] = expected_reference
            try:
                component.Name2 = (
                    f"{record['component_id']}__"
                    f"{record['source_node_id']}"
                    if record.get('source_node_id')
                    else record['component_id']
                )
            except Exception:
                pass
            try:
                component.Select4(False, _empty_dispatch(), False)
                assembly_doc.UnfixComponent()
                assembly_model.ClearSelection2(True)
            except Exception:
                pass
            expected_transform = [
                float(value) for value in record.get('transform')
                or _identity_matrix()
            ]
            transform = None
            try:
                math_utility = _maybe_call(self.sw.GetMathUtility)
                array_data = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    expected_transform,
                )
                raw_transform = math_utility._oleobj_.InvokeTypes(
                    1,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_DISPATCH, 0),
                    ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                    array_data,
                )
                if raw_transform is not None:
                    transform = win32com.client.Dispatch(raw_transform)
            except Exception as exc:
                raise RuntimeError(
                    f"Could not create component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if transform is None:
                raise RuntimeError(
                    f"Could not create component transform for "
                    f"{record['component_id']}"
                )
            try:
                component.Transform2 = transform
            except Exception as exc:
                raise RuntimeError(
                    f"Could not set component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            try:
                actual_transform = component.Transform2
                actual_data = [
                    float(value) for value in actual_transform.ArrayData
                ]
            except Exception as exc:
                raise RuntimeError(
                    f"Could not read component transform for "
                    f"{record['component_id']}: {exc}"
                ) from exc
            if not _transform_matrices_close(
                actual_data, expected_transform
            ):
                raise RuntimeError(
                    f"Component transform readback mismatch for "
                    f"{record['component_id']}: expected="
                    f"{expected_transform[:13]!r} actual="
                    f"{actual_data[:13]!r}"
                )
            inserted.append(component)
            print(
                f'SIMPLECAD_SW_ASSEMBLY_INSERT={insertion_index + 1}/'
                f'{len(component_records)}:{record["component_id"]}',
                flush=True,
            )
        if len(inserted) != len(component_records):
            raise RuntimeError('SolidWorks assembly component count mismatch')
        rebuild_ok = assembly_model.ForceRebuild3(False)
        if rebuild_ok is False:
            raise RuntimeError(
                'Assembly rebuild failed after inserting native components'
            )
        properties = assembly_model.Extension.CustomPropertyManager('')
        self._persist_chunked_json_property(
            properties,
            'SimpleCADComponentMap',
            component_records,
            'simplecad-sw-component-map-v1',
        )
        self._set_document_custom_property(
            properties, 'SimpleCADMasterPartPath', package_master_path
        )
        if self._document_custom_property_value(
            properties, 'SimpleCADMasterPartPath'
        ) != package_master_path:
            raise RuntimeError(
                'assembly master-part property readback mismatch'
            )
        rebuild_ok = assembly_model.ForceRebuild3(False)
        if rebuild_ok is False:
            raise RuntimeError(
                'Assembly rebuild failed after persisting component metadata'
            )
        os.makedirs(assembly_directory, exist_ok=True)
        if os.path.exists(assembly_path):
            os.remove(assembly_path)
        errors = _byref_i4()
        warnings = _byref_i4()
        ok = assembly_model.Extension.SaveAs(
            assembly_path,
            SW_SAVE_AS_CURRENT_VERSION,
            SW_SAVE_AS_OPTIONS_SILENT,
            _empty_dispatch(),
            errors,
            warnings,
        )
        if not ok or not os.path.exists(assembly_path):
            raise RuntimeError(
                f'SolidWorks SaveAs SLDASM failed: ok={ok!r}, '
                f'errors={errors.value}, warnings={warnings.value}'
            )
        self.model = assembly_model
        self._save_step(step_path)
        try:
            self.sw.CloseDoc(master_title)
        except Exception:
            pass
        print(
            'SIMPLECAD_SW_NATIVE_ASSEMBLY=' + assembly_path,
            flush=True,
        )

    def _assembly_template(self):
        return self._document_template(9, 'asmdot')


__all__ = ["AssemblyRuntimeMixin"]
