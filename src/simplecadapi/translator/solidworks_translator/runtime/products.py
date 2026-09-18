"""SolidWorks runtime fragment: BodyProductRuntimeMixin."""


class BodyProductRuntimeMixin:
    def _body_from_value(self, value):
        if hasattr(value, 'GetFaces'):
            return value
        if isinstance(value, dict):
            if value.get('kind') == 'body':
                return self._resolve_body_reference(
                    value.get('body'),
                    value.get('_body_name'),
                    value.get('_body_bbox'),
                    value.get('_body_snapshot'),
                )
            if value.get('kind') == 'part':
                return self._body_from_value(value.get('body'))
            if value.get('kind') == 'compound':
                bodies = self._bodies_from_value(value)
                if len(bodies) == 1:
                    return bodies[0]
                raise RuntimeError(
                    f'Expected one SolidWorks body, got a live body set with '
                    f'{len(bodies)} sections'
                )
        raise RuntimeError(f'Expected a SolidWorks body, got {type(value).__name__}')

    def _bodies_from_value(self, value):
        if isinstance(value, dict) and value.get('kind') == 'compound':
            bodies = [
                body for body in value.get('bodies') or []
                if body is not None
            ]
            if not bodies:
                raise RuntimeError('Expected a non-empty SolidWorks body set')
            return bodies
        return [self._body_from_value(value)]

    def _resolve_body_reference(
        self,
        body,
        expected_name=None,
        expected_bbox=None,
        body_snapshot=None,
    ):
        fresh_bodies = self._solid_bodies()

        def com_identity(entity):
            try:
                unknown = entity._oleobj_.QueryInterface(
                    pythoncom.IID_IUnknown
                )
                return ('com', hash(unknown))
            except Exception:
                return ('python', id(entity))

        if body is not None:
            direct_identity = com_identity(body)
            direct_matches = [
                candidate for candidate in fresh_bodies
                if com_identity(candidate) == direct_identity
            ]
            if len(direct_matches) == 1:
                return direct_matches[0]

        ambiguous = None

        def unique_bbox_candidate(candidates, label):
            nonlocal ambiguous
            ranked = sorted(
                (
                    _bbox_score(
                        self._box_from_entity(candidate), expected_bbox
                    ),
                    index,
                    candidate,
                )
                for index, candidate in enumerate(candidates)
            )
            if not ranked:
                return None
            best_score = ranked[0][0]
            ties = [
                item for item in ranked
                if abs(item[0] - best_score) <= 1.0e-12
            ]
            if len(ties) == 1:
                return ties[0][2]
            ambiguous = (
                f'{label} body lookup tied across {len(ties)} candidates '
                f'at bbox score {best_score}'
            )
            return None

        if expected_name:
            named = [
                candidate for candidate in fresh_bodies
                if self._body_name(candidate) == str(expected_name)
            ]
            if len(named) == 1:
                return named[0]
            if named and isinstance(expected_bbox, dict):
                named_match = unique_bbox_candidate(named, 'named')
                if named_match is not None:
                    return named_match
        if isinstance(expected_bbox, dict):
            expected_size = _distance(
                expected_bbox.get('min'), expected_bbox.get('max')
            )
            if expected_size > 1.0e-12 and fresh_bodies:
                best_body = unique_bbox_candidate(
                    fresh_bodies, 'global'
                )
                if best_body is not None:
                    best_score = _bbox_score(
                        self._box_from_entity(best_body), expected_bbox
                    )
                    if best_score <= max(
                        1.0e-7, expected_size * 1.0e-7
                    ):
                        return best_body
        if ambiguous is not None:
            raise RuntimeError(
                f'Ambiguous SolidWorks body reference for '
                f'name={expected_name!r} bbox={expected_bbox!r}: {ambiguous}'
            )
        if body_snapshot is not None:
            snapshot_bbox = self._box_from_entity(body_snapshot)
            if self._body_faces(body_snapshot) and (
                not isinstance(expected_bbox, dict)
                or _distance(
                    expected_bbox.get('min'), expected_bbox.get('max')
                ) <= 1.0e-12
                or _bbox_score(snapshot_bbox, expected_bbox)
                <= max(
                    1.0e-7,
                    _distance(
                        expected_bbox.get('min'), expected_bbox.get('max')
                    ) * 1.0e-7,
                )
            ):
                return body_snapshot
        if body is not None:
            return body
        raise RuntimeError(
            f'Could not resolve SolidWorks body reference '
            f'name={expected_name!r} bbox={expected_bbox!r}'
        )

    def _bodies_from_product(self, value):
        if isinstance(value, dict) and value.get('kind') == 'part':
            return self._bodies_from_product(value.get('body'))
        if isinstance(value, dict) and value.get('kind') == 'assembly':
            bodies = []
            for component in value.get('components') or []:
                bodies.extend(self._bodies_from_product(component.get('item')))
            return bodies
        if isinstance(value, dict) and value.get('kind') == 'body':
            return [self._body_from_value(value)]
        if isinstance(value, dict) and value.get('kind') == 'compound':
            return [body for body in value.get('bodies') or [] if body is not None]
        return []

    def _product_body_instances(
        self, value, placements=(), path=(), body_node_id=''
    ):
        if isinstance(value, dict) and value.get('kind') == 'part':
            return self._product_body_instances(
                value.get('body'),
                placements,
                path,
                str(value.get('body_node') or body_node_id or ''),
            )
        if isinstance(value, dict) and value.get('kind') == 'assembly':
            instances = []
            for index, component in enumerate(value.get('components') or []):
                component_id = str(
                    component.get('component_id')
                    or (component.get('params') or {}).get('component_id')
                    or index
                )
                component_placement = component.get('placement') or {
                    'kind': 'placement',
                    'params': {},
                }
                instances.extend(
                    self._product_body_instances(
                        component.get('item'),
                        placements + (component_placement,),
                        path + (component_id,),
                        body_node_id,
                    )
                )
            return instances
        if isinstance(value, dict) and value.get('kind') == 'body':
            return [(
                self._body_from_value(value), placements, path, body_node_id
            )]
        if isinstance(value, dict) and value.get('kind') == 'compound':
            return [
                (body, placements, path + (str(index),), body_node_id)
                for index, body in enumerate(value.get('bodies') or [])
                if body is not None
            ]
        return []

    def _materialize_product_bodies(self, value, name_prefix):
        bodies = []
        for (
            body, placements, path, explicit_body_node_id
        ) in self._product_body_instances(value):
            if body is None:
                continue
            matrices = [_placement_matrix(placement) for placement in placements]
            has_transform = any(not _is_identity_matrix(matrix) for matrix in matrices)
            source_name = self._body_name(body)
            source_tokens = source_name.split('_')
            inferred_source_node_id = (
                f'node_{source_tokens[2]}'
                if len(source_tokens) >= 3
                and source_tokens[0] == 'SimpleCAD'
                and source_tokens[1] == 'node'
                else ''
            )
            source_node_id = str(
                explicit_body_node_id or inferred_source_node_id
            )
            dependency_node_ids = sorted(
                self._result_dependency_ids([source_node_id])
            )
            if source_node_id and source_node_id not in dependency_node_ids:
                raise RuntimeError(
                    f'Could not resolve dependency graph for terminal part '
                    f'body {source_node_id}'
                )
            source_owner = ''
            for getter_name in ('GetFeature', 'IGetFeature'):
                try:
                    owner = _maybe_call(getattr(body, getter_name))
                    if owner is not None:
                        source_owner = str(_maybe_call(owner.Name) or '')
                        if source_owner:
                            break
                except Exception:
                    pass
            source_expected_bbox = self._box_from_entity(body)
            # Capture while the terminal branch still exposes a live Body2.
            # The assembly writer first tries a derived part linked to the
            # saved master; this detached body is only the cross-document
            # transport/fallback and must not be captured after Keep Bodies.
            prepared_source_body = self._copy_temp_body(body)
            source_key = source_owner or source_name
            may_reuse_source = (
                not path
                and not has_transform
                and source_key not in self.materialized_source_body_keys
            )
            self.logs.append(
                f'product body path={path!r} owner={source_owner!r} '
                f'name={source_name!r} transformed={has_transform!r} '
                f'reuse_live={may_reuse_source!r}'
            )
            if may_reuse_source:
                self.materialized_source_body_keys.add(source_key)
                bodies.append(body)
                if path:
                    self.assembly_occurrences.append({
                        'component_id': str(path[0]),
                        'path': tuple(str(part) for part in path),
                        'placements': tuple(placements),
                        'body': body,
                        'source_body': body,
                        'prepared_source_body': prepared_source_body,
                        'source_body_name': source_name,
                        'source_owner': source_owner,
                        'source_expected_bbox': source_expected_bbox,
                        'source_node_id': source_node_id,
                        'dependency_node_ids': dependency_node_ids,
                    })
                continue

            self.component_instance_counter += 1
            path_token = '_'.join(str(part) for part in path if str(part))
            instance_name = (
                f'{name_prefix}_{path_token}_{self.component_instance_counter}'
                if path_token
                else f'{name_prefix}_{self.component_instance_counter}'
            )
            can_materialize_live = all(
                _is_identity_matrix(matrix)
                or _is_translation_matrix(matrix)
                for matrix in matrices
            )
            if can_materialize_live:
                # Preserve the unplaced source as a live body in the package
                # master. Translation Move/Copy features may move their input
                # in place, so placements must operate on a dependent copy.
                instance_body = self._transform_body_feature(
                    body,
                    _identity_matrix(),
                    f'{instance_name}_source_copy',
                )
                transformed = False
                for placement_index, matrix in enumerate(reversed(matrices)):
                    if _is_identity_matrix(matrix):
                        continue
                    instance_body = self._transform_body_feature(
                        instance_body,
                        matrix,
                        f'{instance_name}_placement_{placement_index + 1}',
                    )
                    transformed = True
                self.logs.append(
                    f'{instance_name} uses live Move/Copy Body materialization'
                    + (' with placement' if transformed else '')
                )
            else:
                temp_body = self._copy_temp_body(body)
                for matrix in reversed(matrices):
                    if not _is_identity_matrix(matrix):
                        self._apply_transform_to_temp_body(temp_body, matrix)
                self._mark_degraded(instance_name, 'static_component_body')
                instance_body = self._create_feature_from_body(
                    temp_body, instance_name
                )
            bodies.append(instance_body)
            if path:
                self.assembly_occurrences.append({
                    'component_id': str(path[0]),
                    'path': tuple(str(part) for part in path),
                    'placements': tuple(placements),
                    'body': instance_body,
                    'source_body': body,
                    'prepared_source_body': prepared_source_body,
                    'source_body_name': source_name,
                    'source_owner': source_owner,
                    'source_expected_bbox': source_expected_bbox,
                    'source_node_id': source_node_id,
                    'dependency_node_ids': dependency_node_ids,
                })
        return bodies

    def _result_bodies(self):
        if not self.result_node_ids:
            self.result_node_ids = [str(node.get('node_id')) for node in self.nodes[-1:]]
        result_node_ids = list(self.result_node_ids)
        bodies = []
        for node_id in result_node_ids:
            for value in self.outputs.get(str(node_id), []):
                if isinstance(value, dict) and value.get('kind') in {'part', 'assembly'}:
                    if value.get('kind') == 'assembly':
                        bodies.extend(
                            self._materialize_product_bodies(
                                value,
                                f'SimpleCAD_{node_id}_component',
                            )
                        )
                    else:
                        bodies.extend(self._bodies_from_product(value))
                elif isinstance(value, dict) and value.get('kind') == 'body':
                    body = self._body_from_value(value)
                    # SolidWorks Body2 has no editable Placement property. A
                    # zero-displacement Move/Copy Body feature is the native
                    # equivalent for result-level placement edits: it keeps a
                    # live dependency on the reconstructed result while giving
                    # the reopened document persistent TransformX/Y/Z values.
                    body = self._transform_body_feature(
                        body,
                        _identity_matrix(),
                        f'SimpleCAD_{node_id}_placement',
                    )
                    bodies.append(body)
                elif isinstance(value, dict) and value.get('kind') == 'compound':
                    bodies.extend(value.get('bodies') or [])
                elif hasattr(value, 'GetFaces'):
                    bodies.append(value)
        return [body for body in bodies if body is not None]

    def _solid_bodies(self):
        bodies = None
        for call in (
            lambda: self.model.GetBodies2(SW_SOLID_BODY, False),
            lambda: self.model.GetBodies2(SW_SOLID_BODY, True),
        ):
            try:
                bodies = call()
                if bodies:
                    break
            except Exception:
                bodies = None
        if bodies is None:
            return []
        if isinstance(bodies, tuple):
            return list(bodies)
        if isinstance(bodies, list):
            return bodies
        try:
            return list(bodies)
        except Exception:
            return [bodies]

    def _body_name(self, body):
        try:
            return str(body.Name)
        except Exception:
            pass
        try:
            return str(body.GetName())
        except Exception:
            return str(id(body))

    def _body_names(self):
        return {self._body_name(body) for body in self._solid_bodies()}

    def _body_geometry_key(self, body):
        bbox = self._box_from_entity(body)
        coordinates = tuple(
            round(float(value), 9)
            for point in (bbox.get('min'), bbox.get('max'))
            for value in _v3(point)
        )
        return self._body_name(body), coordinates

    def _capture_new_body(
        self, before_names, feature=None, expected_bbox=None, fallback_body=None
    ):
        if feature is not None:
            error, is_warning = _feature_error_status(feature)
            if error and not is_warning:
                raise RuntimeError(f'SolidWorks feature reported error {error}')
            if error and is_warning:
                self.logs.append(f'SolidWorks feature reported warning {error}')
        if feature is None and not before_names and fallback_body is None:
            raise RuntimeError('Cannot capture a feature result without a feature or a pre-operation body snapshot')
        def com_identity(entity):
            try:
                unknown = entity._oleobj_.QueryInterface(
                    pythoncom.IID_IUnknown
                )
                return ('com', hash(unknown))
            except Exception:
                return ('python', id(entity))

        def unique_by_identity(values):
            unique = {}
            for value in values:
                if value is not None:
                    unique.setdefault(com_identity(value), value)
            return list(unique.values())

        feature_candidates = []
        if feature is not None:
            # IFeature.GetBody is obsolete and can return an edit-state proxy.
            # The supported Feature.GetFaces -> Face2.GetBody chain binds the
            # feature to the body it actually produced or modified, which is
            # essential when several document bodies have the same bbox.
            for getter_name in ('GetFaces', 'IGetFaces2'):
                try:
                    faces = _maybe_call(getattr(feature, getter_name))
                except Exception:
                    faces = None
                if not faces:
                    continue
                if not isinstance(faces, (list, tuple)):
                    faces = [faces]
                for face in faces:
                    for body_getter in ('GetBody', 'IGetBody'):
                        try:
                            body = _maybe_call(getattr(face, body_getter))
                        except Exception:
                            body = None
                        if body is not None:
                            try:
                                body = win32com.client.CastTo(body, 'IBody2')
                            except Exception:
                                pass
                            feature_candidates.append(body)
                            break
                if feature_candidates:
                    break
            feature_candidates = unique_by_identity(feature_candidates)
            # Do not mix obsolete GetBody/IGetBody proxies or guessed DISPIDs
            # into these feature-owned bodies. They can refer to old bodies.
        if not feature_candidates and not before_names and fallback_body is None:
            raise RuntimeError('Feature exposes no result faces and no pre-operation body snapshot is available')
        bodies = self._solid_bodies()
        fresh_candidates = [
            body for body in bodies
            if self._body_name(body) not in before_names
        ]
        if feature_candidates:
            # Feature.GetBody can return an edit-state/transient Body2 proxy.
            # Prefer the reopened-document body with the same persistent name
            # so downstream native features can select it and keep dependency
            # propagation alive.
            feature_keys = {
                com_identity(body) for body in feature_candidates
            }
            persistent_matches = [
                body for body in bodies
                if com_identity(body) in feature_keys
            ]
            if not persistent_matches and len(feature_candidates) == 1:
                feature_body = feature_candidates[0]
                feature_name = self._body_name(feature_body)
                persistent_matches = [body for body in bodies if feature_name and self._body_name(body) == feature_name]
                if not persistent_matches:
                    feature_bbox = self._box_from_entity(feature_body)
                    tolerance = max(1e-7, _distance(feature_bbox['min'], feature_bbox['max']) * 1e-7)
                    spatial_matches = [body for body in bodies if _bbox_score(self._box_from_entity(body), feature_bbox) <= tolerance]
                    if len(spatial_matches) == 1:
                        persistent_matches = spatial_matches
            candidates = (
                list(persistent_matches)
                or list(fresh_candidates)
                or list(feature_candidates)
            )
        else:
            # Bodies enumerated from the document are persistent and remain
            # copyable after the feature manager releases its transient proxy.
            candidates = list(fresh_candidates)
        if not candidates:
            raise RuntimeError('Could not identify SolidWorks feature result body')
        if candidates:
            candidates = unique_by_identity(candidates)
            if isinstance(expected_bbox, dict):
                selected = min(
                    candidates,
                    key=lambda body: _bbox_score(
                        self._box_from_entity(body), expected_bbox
                    ),
                )
            else:
                selected = candidates[-1]
            if feature is not None:
                try:
                    feature_name = str(_maybe_call(feature.Name) or '')
                except Exception:
                    feature_name = ''
                if feature_name:
                    try:
                        selected.Name = f'{feature_name}_body'
                    except Exception as exc:
                        self.logs.append(
                            f'could not persist result body name for '
                            f'{feature_name}: {exc}'
                        )
            return selected

    def _box_from_entity(self, entity):
        # GetBodyBox/GetBox are approximate and can change after rebuild.
        # Use support extrema for solid bodies, in canonical millimetres.
        try:
            minimum, maximum = [], []
            for sign, bounds in ((-1.0, minimum), (1.0, maximum)):
                for axis in range(3):
                    direction = [0.0, 0.0, 0.0]
                    direction[axis] = sign
                    result = entity.GetExtremePoint(*direction)
                    if not isinstance(result, (tuple, list)) or len(result) != 4 or not result[0]:
                        raise ValueError('No support extremum returned')
                    bounds.append(float(result[axis + 1]) * M_TO_MM / MODEL_SCALE)
            return {'min': tuple(minimum), 'max': tuple(maximum)}
        except Exception:
            pass
        for call in (lambda: entity.GetBox(), lambda: entity.GetBodyBox()):
            try:
                bbox = _bbox_from_box(call())
                if bbox:
                    return bbox
            except Exception:
                pass
        return {'min': (0.0, 0.0, 0.0), 'max': (0.0, 0.0, 0.0)}

    def _body_volume(self, body):
        try:
            values = body.GetMassProperties(1.0)
            if (
                isinstance(values, (list, tuple))
                and values
                and isinstance(values[0], (list, tuple))
            ):
                values = values[0]
            if isinstance(values, (list, tuple)) and len(values) >= 4:
                volume_m3 = abs(float(values[3]))
                if math.isfinite(volume_m3) and volume_m3 > 0.0:
                    return volume_m3 * (M_TO_MM / MODEL_SCALE) ** 3
        except Exception:
            pass
        return None


__all__ = ["BodyProductRuntimeMixin"]
