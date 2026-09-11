"""SolidWorks runtime fragment: FeatureRuntimeMixin."""


class FeatureRuntimeMixin:
    def _modeler(self):
        # The SolidWorks application object does not expose type information to
        # late-bound pywin32 clients, so GetModeler is unavailable by name even
        # though it is part of ISldWorks. DISP ID 34 is the documented
        # ISldWorks::GetModeler entry in the installed type library.
        raw_modeler = self.sw._oleobj_.InvokeTypes(
            34,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (),
        )
        if raw_modeler is None:
            raise RuntimeError('SolidWorks did not provide the geometry modeler')
        return win32com.client.Dispatch(
            raw_modeler,
            resultCLSID='{83A33D73-27C5-11CE-BFD4-00400513BB57}',
        )

    def _create_loft_temp_body(self, sketches, args, *, use_legacy=True):
        modeler = self._modeler()
        # CreateLoftBody consumes the currently selected section sketches and
        # is available on older SolidWorks versions where the FeatureManager
        # loft signatures return None for the same selection.
        raw_body = None
        if use_legacy:
            raw_body = modeler._oleobj_.InvokeTypes(
                115,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (
                    (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                    (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                ),
                self.model,
                False,
                False,
                False,
                True,
                1.0,
                0,
                0,
            )
        if raw_body is not None:
            return win32com.client.Dispatch(raw_body)
        raw_body = modeler._oleobj_.InvokeTypes(
            122,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
            ),
            self.model,
            tuple(sketches),
            None,
            None,
            *args,
        )
        return win32com.client.Dispatch(raw_body) if raw_body is not None else None

    def _create_swept_temp_body(self, args):
        modeler = self._modeler()
        raw_body = modeler._oleobj_.InvokeTypes(
            102,
            0,
            pythoncom.DISPATCH_METHOD,
            (pythoncom.VT_DISPATCH, 0),
            (
                (pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_I2, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_R8, pythoncom.PARAMFLAG_FIN),
                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
            ),
            self.model,
            *args,
        )
        return win32com.client.Dispatch(raw_body) if raw_body is not None else None

    def _extrude_profile(self, profile, params, node_id):
        direction = _unit(params.get('direction') or self._profile_normal(profile))
        distance = float(params.get('distance', 0.0))
        if abs(distance) <= 1.0e-12:
            raise RuntimeError('Extrude distance is zero')
        before = self._body_names()
        terminal_part_feature = self._is_terminal_part_feature(node_id)
        # Prefer a native sketch plane at the profile's actual offset even for
        # intermediate Extrudes. The old non-terminal path created the feature
        # at a reference plane and then inserted a static transform body,
        # severing downstream parameter propagation after reopen.
        use_native_profile_offset = True
        try:
            sketch_obj, offset, dominant, sketch_normal, _axis_entity = self._create_profile_sketch(
                profile,
                direction,
                f'SimpleCADSketch_{node_id}',
                use_profile_offset=use_native_profile_offset,
            )
        except RuntimeError as exc:
            if 'profile offset plane' not in str(exc):
                raise
            self._clear_selection()
            self._mark_degraded(
                f'SimpleCAD_{node_id}_offset',
                'static_terminal_extrude_offset',
            )
            use_native_profile_offset = False
            sketch_obj, offset, dominant, sketch_normal, _axis_entity = self._create_profile_sketch(
                profile,
                direction,
                f'SimpleCADSketch_{node_id}',
                use_profile_offset=False,
            )
        try:
            if sketch_obj is not None:
                self._clear_selection()
                self._select_entity(sketch_obj)
        except Exception:
            pass
        reverse_direction = _dot(direction, sketch_normal) < 0.0 or distance < 0.0
        feature = self.model.FeatureManager.FeatureExtrusion2(
            True, False, bool(reverse_direction),
            0, 0,
            _as_m(abs(distance)), 0.0,
            False, False, False, False,
            0.0, 0.0,
            False, False, False, False,
            False, False, False,
            0.0, 0.0,
            False,
        )
        if feature is None:
            raise RuntimeError('SolidWorks did not create the extrude feature')
        try:
            feature.Name = f'SimpleCAD_{node_id}_extrude'
        except Exception:
            pass
        body = self._capture_new_body(before, feature)
        if abs(offset) > 1.0e-9 and not use_native_profile_offset:
            vector = (0.0, 0.0, 0.0)
            if dominant == 0:
                vector = (offset, 0.0, 0.0)
            elif dominant == 1:
                vector = (0.0, offset, 0.0)
            else:
                vector = (0.0, 0.0, offset)
            body = self._transform_body_feature(body, _translation_matrix(vector), f'SimpleCAD_{node_id}_offset')
        return body

    def _revolve_profile(self, profile, params, node_id):
        axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
        origin = _v3(params.get('origin') or (0.0, 0.0, 0.0))
        profile_normal = self._profile_normal(profile)
        sketch_obj, _offset, _dominant, _normal, axis_entity = self._create_profile_sketch(
            profile,
            profile_normal,
            f'SimpleCADSketch_{node_id}',
            use_profile_offset=True,
            revolve_axis=(origin, axis),
        )
        self.logs.append(f'revolve native feature requested for {node_id}; using SolidWorks FeatureRevolve2 fallback signatures')
        before = self._body_names()
        angle = math.radians(float(params.get('angle', 360.0)))
        feature = None
        attempt_states = []

        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        sketch_regions = self._sketch_regions(sketch_obj)
        sketch_contours = self._sketch_contours(sketch_obj)
        segment_gaps = self._sketch_segment_endpoint_gaps(sketch_obj)
        profile_state = {
            'segments': len(self._sketch_segments(sketch_obj)),
            'regions': len(sketch_regions),
            'contours': len(sketch_contours),
            'gaps': segment_gaps,
        }
        self.logs.append(
            f'revolve profile state for {node_id}: {profile_state!r}'
        )

        def select_revolve_inputs(include_axis, use_region=False):
            self._clear_selection()
            profile_entity = sketch_regions[0] if use_region and sketch_regions else sketch_obj
            if profile_entity is None or not self._select_entity(profile_entity):
                raise RuntimeError(f'Could not select the revolve profile for {node_id}')
            if include_axis:
                if axis_entity is None or not self._select_entity(axis_entity, append=True, mark=4):
                    raise RuntimeError(f'Could not select the revolve axis for {node_id}')
            return self._selection_state()

        attempts = (
            (
                'FeatureRevolve2',
                True,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve2WithoutAxis',
                False,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve2Region',
                True,
                False,
                True,
                lambda: self.model.FeatureManager.FeatureRevolve2(
                    True, True, False, False, False, False,
                    0, 0, abs(angle), 0.0,
                    False, False, 0.0, 0.0,
                    0, 0.0, 0.0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolve',
                True,
                False,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve(
                    abs(angle), False, 0.0, 0, 0,
                    False, False, True,
                ),
            ),
            (
                'FeatureRevolveScoped',
                True,
                True,
                False,
                lambda: self.model.FeatureManager.FeatureRevolve(
                    abs(angle), False, 0.0, 0, 0,
                    False, True, True,
                ),
            ),
        )
        for api_name, include_axis, use_scope, use_region, create_feature in attempts:
            try:
                if use_region and not sketch_regions:
                    continue
                selection_state = select_revolve_inputs(include_axis, use_region)
                attempt_states.append({
                    'api': api_name,
                    'include_axis': include_axis,
                    'use_scope': use_scope,
                    'use_region': use_region,
                    'selections': selection_state,
                })
                feature = create_feature()
                if feature is not None:
                    break
                self.logs.append(
                    f'revolve {api_name} attempt returned no feature for {node_id}; '
                    f'include_axis={include_axis} use_scope={use_scope} '
                    f'selections={selection_state!r}'
                )
            except Exception as exc:
                self.logs.append(
                    f'revolve {api_name} attempt failed for {node_id}: {exc}'
                )
        if feature is None:
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks revolve feature creation failed; profile={profile_state!r}; '
                f'attempts={attempt_states!r}; '
                f'logs={self.logs[-4:]!r}'
            )
        return self._capture_new_body(before, feature)

    def _loft_profiles(self, profiles, params, node_id):
        if bool(params.get('ruled')) and len(profiles) > 2:
            segment_bodies = []
            for index in range(len(profiles) - 1):
                segment_params = dict(params)
                segment_params['ruled'] = False
                segment_params['_ruled_segment'] = True
                segment_params['profile_count'] = 2
                segment_bodies.append(self._loft_profiles(
                    profiles[index:index + 2],
                    segment_params,
                    f'{node_id}_ruled_{index + 1}',
                ))
                segment_body = segment_bodies[-1]
                segment_bodies[-1] = {
                    'kind': 'body', 'body': segment_body,
                    '_body_name': self._body_name(segment_body),
                    '_body_bbox': self._box_from_entity(segment_body),
                }
            self.logs.append(
                f'loft {node_id} preserved ruled topology as '
                f'{len(segment_bodies)} adjacent two-section lofts'
            )
            segment_bodies = [self._body_from_value(value) for value in segment_bodies]
            result = self._boolean_body(
                segment_bodies[0],
                segment_bodies[1:],
                SWBODYADD,
                f'SimpleCAD_{node_id}_ruled',
                clean=False,
                prefer_native=True,
            )
            return result
        self.logs.append(f'loft native feature requested for {node_id}; using SolidWorks blend fallback signatures')
        # Native Loft exposes its result through Feature.GetFaces ->
        # Face2.GetBody. Avoid a document-wide body scan before every ruled
        # segment; large models can contain hundreds of prior feature bodies.
        before = self._body_names()
        self._clear_selection()
        sketches = []
        for index, profile in enumerate(profiles):
            sketch_obj, _offset, _dominant, normal, _axis_entity = self._create_profile_sketch(
                profile,
                self._profile_normal(profile),
                f'SimpleCADSketch_{node_id}_{index}',
                use_profile_offset=True,
            )
            if sketch_obj is not None:
                sketches.append(sketch_obj)
        profile_states = []
        for sketch_obj in sketches:
            contours = []
            sketch = None
            try:
                sketch = _maybe_call(sketch_obj.GetSpecificFeature2)
            except Exception:
                pass
            if sketch is not None:
                try:
                    raw_contours = _maybe_call(sketch.GetSketchContours)
                except Exception:
                    raw_contours = None
                if raw_contours:
                    raw_contours = (
                        list(raw_contours)
                        if isinstance(raw_contours, (list, tuple))
                        else [raw_contours]
                    )
                    for contour in raw_contours:
                        try:
                            contours.append(bool(_maybe_call(contour.IsClosed)))
                        except Exception:
                            contours.append(None)
            profile_states.append({
                'segments': len(self._sketch_segments(sketch_obj)),
                'contours_closed': contours,
            })
        try:
            profile_edge_groups = [
                list(self._profile_edges(profile)) for profile in profiles
            ]
            dense_polyline_profiles = bool(profile_edge_groups) and all(
                len(edges) >= 32
                and all(edge.get('type') == 'line' for edge in edges)
                for edges in profile_edge_groups
            )
        except Exception:
            dense_polyline_profiles = False
        modeler_loft_args = (
            (
                False, 0, 0.0, 0.0,
                True, False, True, False, True, 1.0,
                1.0, 1.0, True, True, 1, 1, False,
            ),
            (
                False, 0, 0.0, 0.0,
                False, False, False, False, True, 1.0,
                0.0, 0.0, True, True, 0, 0, False,
            ),
        )
        def select_sections(
            section_sketches,
            selection_mode='sketch',
            segment_offsets=None,
        ):
            self._clear_selection()
            for index, sketch_obj in enumerate(section_sketches):
                entity = sketch_obj
                if selection_mode == 'sketch_name':
                    # Whole-sketch selection by name: SW accepts "SKETCH"
                    # selections for loft profiles even when contour/segment
                    # introspection returns nothing (dense polyline loops).
                    try:
                        sketch_name = str(_maybe_call(sketch_obj.Name))
                    except Exception:
                        sketch_name = ''
                    if not sketch_name or not bool(
                        self.model.Extension.SelectByID2(
                            sketch_name,
                            'SKETCH',
                            0.0, 0.0, 0.0,
                            index > 0,
                            1,
                            _empty_dispatch(),
                            0,
                        )
                    ):
                        raise RuntimeError(
                            f'Could not select SolidWorks loft profile sketch '
                            f'{sketch_name!r} by name for {node_id}'
                        )
                    continue
                if selection_mode == 'sketch_pick':
                    vertices = self._linear_profile_vertices(profiles[index])
                    if not vertices:
                        raise RuntimeError(
                            f'No linear profile vertices for SolidWorks loft '
                            f'pick point {index} in {node_id}'
                        )
                    offset = 0
                    if segment_offsets and index < len(segment_offsets):
                        offset = int(segment_offsets[index])
                    point = vertices[offset % len(vertices)]
                    try:
                        sketch_name = str(_maybe_call(sketch_obj.Name))
                    except Exception:
                        sketch_name = ''
                    if not sketch_name or not bool(
                        self.model.Extension.SelectByID2(
                            sketch_name,
                            'SKETCH',
                            float(point[0]) * MM_TO_M,
                            float(point[1]) * MM_TO_M,
                            float(point[2]) * MM_TO_M,
                            index > 0,
                            1,
                            _empty_dispatch(),
                            0,
                        )
                    ):
                        raise RuntimeError(
                            f'Could not select SolidWorks loft profile {index} '
                            f'at canonical pick point {point!r} for {node_id}'
                        )
                    continue
                if selection_mode == 'contour':
                    contours = self._sketch_contours(sketch_obj)
                    if contours:
                        entity = contours[0]
                elif selection_mode == 'segment':
                    segments = self._sketch_segments(sketch_obj)
                    if segments:
                        offset = 0
                        if segment_offsets and index < len(segment_offsets):
                            offset = int(segment_offsets[index])
                        entity = segments[offset % len(segments)]
                if not self._select_entity(entity, append=index > 0, mark=1):
                    raise RuntimeError(
                        f'Could not select SolidWorks loft profile {index} '
                        f'using {selection_mode} for {node_id}'
                    )
            return self._selection_state()

        def create_native_loft(
            section_sketches,
            section_label,
            selection_mode='sketch',
            segment_offsets=None,
        ):
            selection = select_sections(
                section_sketches, selection_mode, segment_offsets
            )
            tangent_attempt = (
                ('Blend2TangentCompatibility', lambda: self.model.FeatureManager.InsertProtrusionBlend2(
                    False, True, False, 1.0,
                    0, 0,
                    1.0, 1.0,
                    True, True,
                    False, 0.0, 0.0, 0,
                    False, True, True,
                    2,
                )),
            )
            unconstrained_attempts = (
                ('Blend2Unconstrained', lambda: self.model.FeatureManager.InsertProtrusionBlend2(
                    False, False, False, 1.0,
                    0, 0,
                    0.0, 0.0,
                    False, False,
                    False, 0.0, 0.0, 0,
                    False, False, True,
                    2,
                )),
                ('BlendLegacy', lambda: self.model.FeatureManager.InsertProtrusionBlend(
                    False, False, False, 1.0,
                    0, 0,
                    0.0, 0.0,
                    False, False,
                    False, 0.0, 0.0, 0,
                    False, False, True,
                )),
            )
            attempts = (
                unconstrained_attempts + tangent_attempt
                if params.get('_ruled_segment')
                else tangent_attempt + unconstrained_attempts
            )
            for attempt_name, attempt in attempts:
                try:
                    candidate = attempt()
                    if candidate is not None:
                        self.logs.append(
                            f'loft {node_id} {section_label} used {attempt_name}'
                        )
                        return candidate, selection
                except Exception as exc:
                    self.logs.append(
                        f'loft {attempt_name} attempt failed for '
                        f'{node_id} {section_label}: {exc}'
                    )
            self.logs.append(
                f'loft attempts returned no feature for {node_id} {section_label}; '
                f'sections={len(section_sketches)} selections={selection!r}'
            )
            return None, selection

        # Prefer editable loft features for every profile, including polylines.
        # Temporary modeler bodies have no sketch-to-feature dependency.

        initial_selection_mode = (
            'segment' if params.get('_ruled_segment') else 'sketch'
        )
        initial_segment_offsets = None
        feature, selection_state = create_native_loft(
            sketches,
            'all sections',
            initial_selection_mode,
            initial_segment_offsets,
        )
        if feature is None:
            for selection_mode in ('sketch_name', 'sketch', 'contour', 'segment'):
                if selection_mode == initial_selection_mode:
                    continue
                try:
                    feature, selection_state = create_native_loft(
                        sketches, selection_mode, selection_mode
                    )
                except Exception as exc:
                    self.logs.append(
                        f'loft {selection_mode} selection failed for {node_id}: {exc}'
                    )
                    feature = None
                if feature is not None:
                    break
        if (
            feature is None
            and not params.get('_ruled_segment')
            and len(profiles) > 10
        ):
            # SW's blend feature rejects lofts over a section-count ceiling
            # that depends on profile complexity (10 for dense polyline
            # sections). Rebuild as chained native lofts of <=10 sections,
            # adjacent chunks sharing their boundary section, then union
            # the chunks with a live native Combine feature.
            chunk_bodies = []
            last_start = len(profiles) - 10
            starts = []
            start = 0
            while start < last_start:
                starts.append(start)
                start += 8
            starts.append(last_start)
            for chunk_start in starts:
                chunk_profiles = profiles[chunk_start:chunk_start + 10]
                chunk_params = dict(params)
                chunk_params['profile_count'] = len(chunk_profiles)
                chunk_params['ruled'] = False
                chunk_bodies.append(self._loft_profiles(
                    chunk_profiles,
                    chunk_params,
                    f'{node_id}_chunk{chunk_start}',
                ))
                chunk_body = chunk_bodies[-1]
                chunk_bodies[-1] = {
                    'kind': 'body', 'body': chunk_body,
                    '_body_name': self._body_name(chunk_body),
                    '_body_bbox': self._box_from_entity(chunk_body),
                }
            if chunk_bodies:
                chunk_bodies = [self._body_from_value(value) for value in chunk_bodies]
                self.logs.append(
                    f'loft {node_id} rebuilt as {len(chunk_bodies)} chained '
                    f'native chunk lofts (sections={len(profiles)})'
                )
                return self._boolean_body(
                    chunk_bodies[0],
                    chunk_bodies[1:],
                    SWBODYADD,
                    f'SimpleCAD_{node_id}_chunked',
                    clean=False,
                    prefer_native=True,
                )
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks loft feature creation failed; profiles={len(sketches)}; '
                f'profile_states={profile_states!r}; selections={selection_state!r}; '
                f'logs={self.logs[-6:]!r}'
            )
        if feature is None:
            for modeler_args in modeler_loft_args:
                try:
                    temp_body = self._create_loft_temp_body(sketches, modeler_args)
                    if temp_body is not None:
                        return self._create_feature_from_body(
                            temp_body, f'SimpleCAD_{node_id}_loft'
                        )
                except Exception as exc:
                    self.logs.append(
                        f'temporary loft body attempt failed for {node_id}: {exc}'
                    )
        if feature is None:
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks loft feature creation failed for {node_id}; '
                f'profiles={len(sketches)}; profile_states={profile_states!r}; '
                f'selections={selection_state!r}; logs={self.logs[-6:]!r}'
            )
        return self._capture_new_body(before, feature)

    def _single_helix_edge(self, path):
        try:
            edges = list(self._profile_edges(path))
        except Exception:
            return None
        if len(edges) == 1 and edges[0].get('type') == 'helix':
            return edges[0]
        return None

    def _create_helix_path(self, helix, node_id):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            raise RuntimeError(
                f'SolidWorks helix requires positive radius, pitch, and height; '
                f'params={params!r}'
            )

        circle_profile = {
            'kind': 'wire',
            'edges': [{
                'kind': 'edge',
                'type': 'circle',
                'center': center,
                'radius': radius,
                'normal': axis,
            }],
        }
        circle_sketch, _offset, _dominant, _normal, _axis_entity = self._create_profile_sketch(
            circle_profile,
            axis,
            f'SimpleCADSketch_{node_id}_helix_base',
            use_profile_offset=True,
        )

        before = {
            self._feature_identity(feature)
            for feature in self._features()
        }
        self._clear_selection()
        if not self._select_entity(circle_sketch, append=False):
            raise RuntimeError(f'Could not select the helix base sketch for {node_id}')

        # swHelixDefinedByHeightAndPitch = 2. InsertHelix creates the native
        # feature but returns no dispatch object, so identify it geometrically
        # through the newly added feature rather than by a tree position.
        dominant = max(range(3), key=lambda index: abs(axis[index]))
        reverse_direction = axis[dominant] < 0.0
        revolutions = height / pitch
        self.model.InsertHelix(
            reverse_direction,
            True,
            False,
            False,
            2,
            _as_m(height),
            _as_m(pitch),
            revolutions,
            0.0,
            0.0,
        )
        helix_features = [
            feature
            for feature in self._features({'Helix'})
            if self._feature_identity(feature) not in before
        ]
        if not helix_features:
            raise RuntimeError(f'SolidWorks did not create the native helix for {node_id}')
        feature = helix_features[-1]
        try:
            feature.Name = f'SimpleCADHelix_{node_id}'
        except Exception:
            pass
        return feature

    def _helix_edge_selector(self, helix):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            return None

        # SolidWorks may expose a native helix as a feature, a body, or a
        # single edge depending on the installed version. Build a geometric
        # signature for the expected helix and match among all exposed edges;
        # never rely on the order returned by GetEdges().
        axis_index = max(range(3), key=lambda index: abs(axis[index]))
        expected_min = list(center)
        expected_max = list(center)
        for index in range(3):
            radial = radius * math.sqrt(max(0.0, 1.0 - axis[index] * axis[index]))
            expected_min[index] -= radial
            expected_max[index] += radial
        if axis[axis_index] >= 0.0:
            expected_max[axis_index] += height
        else:
            expected_min[axis_index] -= height
        expected_center = tuple(
            (expected_min[index] + expected_max[index]) * 0.5
            for index in range(3)
        )
        expected_length = math.hypot(
            2.0 * math.pi * radius * (height / pitch), height
        )
        return {
            'bbox': {'min': tuple(expected_min), 'max': tuple(expected_max)},
            'center': expected_center,
            'length': expected_length,
        }

    def _helix_feature_edges(self, feature, helix):
        candidates = []
        objects = [feature]
        for getter_name in ('GetSpecificFeature2', 'GetBody', 'IGetBody2'):
            try:
                value = _maybe_call(getattr(feature, getter_name))
                if value is not None:
                    objects.append(value)
            except Exception:
                pass
        seen = set()
        for owner in objects:
            try:
                raw_edges = _maybe_call(owner.GetEdges)
            except Exception:
                raw_edges = None
            if not raw_edges:
                continue
            edges = list(raw_edges) if isinstance(raw_edges, (list, tuple)) else [raw_edges]
            for edge in edges:
                identity = self._feature_identity(edge)
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    candidates.append((edge, self._edge_signature(edge)))
                except Exception as exc:
                    self.logs.append(f'helix edge signature failed: {exc}')
        if not candidates:
            return None

        selector = self._helix_edge_selector(helix)
        if selector is None:
            return None
        try:
            edge = _best_by_geometry(candidates, selector, 'helix path edge')
            return edge
        except Exception as exc:
            self.logs.append(f'helix geometric edge match failed: {exc}')
            return None

    def _sampled_helix_path(self, helix):
        params = dict(helix.get('params') or {})
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        radius = abs(float(params.get('radius', 0.0)))
        pitch = abs(float(params.get('pitch', 0.0)))
        height = abs(float(params.get('height', 0.0)))
        if radius <= TOL or pitch <= TOL or height <= TOL:
            raise RuntimeError(f'Invalid helix path parameters: {params!r}')
        x_axis, y_axis = _plane_axes(axis)
        turns = height / pitch
        # Keep enough points for a stable sweep while bounding the size of
        # generated scripts for long, fine-pitch helices.
        samples = max(32, min(512, int(math.ceil(turns * 8.0)) + 1))
        points = []
        signed_height = height if _dot(axis, _unit(params.get('dir') or axis)) >= 0.0 else -height
        for index in range(samples):
            fraction = index / float(samples - 1)
            angle = 2.0 * math.pi * turns * fraction
            radial = _add(
                _mul(x_axis, radius * math.cos(angle)),
                _mul(y_axis, radius * math.sin(angle)),
            )
            points.append(_add(_add(center, radial), _mul(axis, signed_height * fraction)))
        degree = min(3, len(points) - 1)
        last_knot = len(points) - degree
        knots = [float(index) for index in range(last_knot + 1)]
        multiplicities = [degree + 1]
        multiplicities.extend([1] * max(0, len(knots) - 2))
        multiplicities.append(degree + 1)
        return {
            'kind': 'wire',
            'edges': [{
                'kind': 'edge',
                'type': 'spline',
                'controls': points,
                'degree': degree,
                'knots': knots,
                'multiplicities': multiplicities,
                'weights': [],
                'periodic': False,
            }],
        }

    def _helix_clearance_profile(self, profile, helix):
        params = dict(helix.get('params') or {})
        axis = _unit(params.get('dir') or params.get('axis') or (0.0, 0.0, 1.0))
        center = _v3(params.get('center') or (0.0, 0.0, 0.0))
        pitch = abs(float(params.get('pitch', 0.0)))
        points = self._profile_points(profile)
        if pitch <= TOL or len(points) < 2:
            return profile
        projections = [_dot(point, axis) for point in points]
        span = max(projections) - min(projections)
        if span < pitch * (1.0 - 1.0e-8):
            return profile
        factor = min(1.0, pitch * (1.0 - 1.0e-5) / span)
        if factor >= 1.0:
            return profile

        adjusted = json.loads(json.dumps(profile))
        anchor = _dot(center, axis)

        def adjust_point(point):
            point = _v3(point)
            axial = _dot(point, axis) - anchor
            return _add(point, _mul(axis, axial * (factor - 1.0)))

        for edge in self._profile_edges(adjusted):
            for key in ('start', 'middle', 'end', 'center'):
                if isinstance(edge.get(key), (list, tuple)):
                    edge[key] = adjust_point(edge[key])
            for key in ('controls', 'control_points', 'points'):
                if isinstance(edge.get(key), list):
                    edge[key] = [adjust_point(point) for point in edge[key]]
        self.logs.append(
            f'helix profile axial clearance applied: span={span:.9g} '
            f'pitch={pitch:.9g} factor={factor:.9g}'
        )
        return adjusted

    def _sweep_round_arc_fallback(self, profile, path, node_id):
        profile_edges = list(self._profile_edges(profile))
        path_edges = list(self._profile_edges(path))
        if len(profile_edges) != 1 or len(path_edges) != 1:
            return None
        profile_edge = profile_edges[0]
        arc = path_edges[0]
        if (
            profile_edge.get('type') != 'circle'
            or arc.get('type') != 'angle_arc'
        ):
            return None
        radius = abs(float(profile_edge.get('radius', 0.0)))
        major_radius = abs(float(arc.get('radius', 0.0)))
        if radius <= TOL or major_radius <= radius + TOL:
            return None
        start_angle = float(arc.get('start_angle', 0.0))
        end_angle = float(arc.get('end_angle', 0.0))
        span = (end_angle - start_angle) % (2.0 * math.pi)
        if span <= TOL:
            return None
        normal = _unit(arc.get('normal') or (0.0, 0.0, 1.0))
        center = _v3(arc.get('center'))
        start_point = _angle_arc_world_point(
            center,
            major_radius,
            start_angle,
            normal,
            arc.get('_kernel_x_axis'),
            arc.get('_kernel_y_axis'),
        )
        tangent = _unit(_cross(normal, _sub(start_point, center)))
        arc_profile = {
            'kind': 'face',
            'outer': {
                'kind': 'wire',
                'edges': [{
                    'kind': 'edge',
                    'type': 'circle',
                    'center': start_point,
                    'radius': radius,
                    'normal': tangent,
                }],
            },
            'inners': [],
            'normal': tangent,
        }
        body = self._revolve_profile(
            arc_profile,
            {
                'origin': center,
                'axis': normal,
                'angle': math.degrees(span),
            },
            f'{node_id}_arc_path',
        )
        self.logs.append(
            f'round single-arc sweep fallback used for {node_id}; '
            f'span={span:.9g}'
        )
        return body

    def _sweep_round_line_arc_fallback(self, profile, path, node_id):
        """Build a circular line-arc-line sweep from native cylinders and a revolve."""
        profile_edges = list(self._profile_edges(profile))
        path_edges = list(self._profile_edges(path))
        if len(profile_edges) != 1 or len(path_edges) != 3:
            return None
        profile_edge = profile_edges[0]
        if profile_edge.get('type') != 'circle':
            return None
        if [edge.get('type') for edge in path_edges] != [
            'line', 'angle_arc', 'line'
        ]:
            return None

        radius = abs(float(profile_edge.get('radius', 0.0)))
        arc = path_edges[1]
        major_radius = abs(float(arc.get('radius', 0.0)))
        if radius <= TOL or major_radius <= radius + TOL:
            return None
        normal = _unit(arc.get('normal') or (0.0, 0.0, 1.0))
        start_angle = float(arc.get('start_angle', 0.0))
        end_angle = float(arc.get('end_angle', 0.0))
        span = end_angle - start_angle
        if abs(span) <= TOL or abs(span) >= 2.0 * math.pi - TOL:
            return None
        start_point = _angle_arc_world_point(
            arc.get('center'), major_radius, start_angle, normal,
            arc.get('_kernel_x_axis'), arc.get('_kernel_y_axis')
        )
        end_point = _angle_arc_world_point(
            arc.get('center'), major_radius, end_angle, normal,
            arc.get('_kernel_x_axis'), arc.get('_kernel_y_axis')
        )
        first_line, last_line = path_edges[0], path_edges[2]
        join_tolerance = max(TOL, major_radius * 1.0e-7)
        if (
            _distance(first_line.get('end'), start_point) > join_tolerance
            or _distance(last_line.get('start'), end_point) > join_tolerance
        ):
            return None

        def line_body(index, line):
            start = _v3(line.get('start'))
            end = _v3(line.get('end'))
            vector = _sub(end, start)
            distance = _norm(vector)
            if distance <= TOL:
                return None
            line_profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [{
                        'kind': 'edge',
                        'type': 'circle',
                        'center': start,
                        'radius': radius,
                        'normal': _unit(vector),
                    }],
                },
                'inners': [],
                'normal': _unit(vector),
            }
            return self._extrude_profile(
                line_profile,
                {'direction': _unit(vector), 'distance': distance},
                f'{node_id}_segment_{index}',
            )

        radial = _sub(start_point, _v3(arc.get('center')))
        tangent = _unit(_cross(normal, radial))
        revolve_axis = normal
        if span < 0.0:
            tangent = _mul(tangent, -1.0)
            revolve_axis = _mul(normal, -1.0)
        first_vector = _sub(
            _v3(first_line.get('end')), _v3(first_line.get('start'))
        )
        last_vector = _sub(
            _v3(last_line.get('end')), _v3(last_line.get('start'))
        )
        if _norm(first_vector) <= TOL or _norm(last_vector) <= TOL:
            return None
        end_radial = _sub(end_point, _v3(arc.get('center')))
        end_tangent = _unit(_cross(normal, end_radial))
        if span < 0.0:
            end_tangent = _mul(end_tangent, -1.0)
        tangent_tolerance = 1.0e-7
        first_join_dot = _dot(_unit(first_vector), tangent)
        last_join_dot = _dot(end_tangent, _unit(last_vector))
        first_join_tangent = first_join_dot >= 1.0 - tangent_tolerance
        last_join_tangent = last_join_dot >= 1.0 - tangent_tolerance

        first_body = line_body(0, first_line)
        if first_body is None:
            return None
        bodies = [first_body]
        if first_join_tangent:
            arc_profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [{
                        'kind': 'edge',
                        'type': 'circle',
                        'center': start_point,
                        'radius': radius,
                        'normal': tangent,
                    }],
                },
                'inners': [],
                'normal': tangent,
            }
            arc_body = self._revolve_profile(
                arc_profile,
                {
                    'origin': _v3(arc.get('center')),
                    'axis': revolve_axis,
                    'angle': math.degrees(abs(span)),
                },
                f'{node_id}_arc',
            )
            bodies.append(arc_body)
            if last_join_tangent:
                last_body = line_body(2, last_line)
                if last_body is None:
                    return None
                bodies.append(last_body)
            else:
                self.logs.append(
                    f'round sweep {node_id} stopped solid propagation after '
                    f'non-tangent arc-line join; dot='
                    f'{last_join_dot:.9g}'
                )
        else:
            self.logs.append(
                f'round sweep {node_id} stopped solid propagation after '
                f'non-tangent line-arc join; dot='
                f'{first_join_dot:.9g}'
            )
        result = self._boolean_body(
            bodies[0], bodies[1:], SWBODYADD,
            f'SimpleCAD_{node_id}_round_path', clean=True,
        )
        self.logs.append(f'round line-arc-line sweep fallback used for {node_id}')
        return result

    def _sweep_profile(self, profile, path, params, node_id):
        self.logs.append(f'sweep native feature requested for {node_id}; using SolidWorks sweep fallback signatures')
        try:
            arc_fallback = self._sweep_round_arc_fallback(
                profile, path, node_id
            )
            if arc_fallback is not None:
                return arc_fallback
        except Exception as exc:
            self.logs.append(f'round arc sweep fallback failed for {node_id}: {exc}')
        try:
            round_fallback = self._sweep_round_line_arc_fallback(
                profile, path, node_id
            )
            if round_fallback is not None:
                return round_fallback
        except Exception as exc:
            self.logs.append(f'round sweep fallback failed for {node_id}: {exc}')
        helix_edge = self._single_helix_edge(path)
        frenet_helix_twist = None
        if helix_edge is not None:
            profile = self._helix_clearance_profile(profile, helix_edge)
            if bool(params.get('is_frenet')):
                helix_params = dict(helix_edge.get('params') or {})
                helix_pitch = abs(float(helix_params.get('pitch', 0.0)))
                helix_height = abs(float(helix_params.get('height', 0.0)))
                if helix_pitch > TOL and helix_height > TOL:
                    # _create_helix_path requests a clockwise SolidWorks
                    # helix.  Rotate the section by the same signed number of
                    # turns so its radial axis follows OCC's Frenet frame.
                    frenet_helix_twist = (
                        -2.0 * math.pi * helix_height / helix_pitch
                    )
        before = self._body_names()
        self._clear_selection()
        profile_sketch, _offset, _dominant, _normal, _profile_axis = self._create_profile_sketch(
            profile,
            self._profile_normal(profile),
            f'SimpleCADSketch_{node_id}_profile',
            use_profile_offset=True,
        )
        if helix_edge is not None:
            # Keep the native helix path as the first attempt. Some SolidWorks
            # versions accept the helix feature itself even when it does not
            # expose a selectable edge. The sampled path is a local fallback.
            path_sketch = self._create_helix_path(helix_edge, node_id)
            path_edge = self._helix_feature_edges(path_sketch, helix_edge)
            path_selection_kind = 'helix'
        else:
            path_edge = None
            try:
                path_sketch, _path_offset, _path_dominant, _path_normal, _path_axis = self._create_profile_sketch(
                    path,
                    self._profile_normal(path),
                    f'SimpleCADSketch_{node_id}_path',
                    use_profile_offset=True,
                )
                path_selection_kind = 'sketch'
            except RuntimeError as exc:
                if 'profile is not planar' not in str(exc):
                    raise
                path_sketch = self._create_3d_path_sketch(
                    path, f'SimpleCADSketch_{node_id}_3d_path'
                )
                path_selection_kind = '3d_sketch'
        feature = None
        successful_sweep_body = None
        successful_sweep_attempt = None
        attempt_states = []
        path_segments = (
            self._sketch_segments(path_sketch)
            if path_sketch is not None and helix_edge is None
            else []
        )
        if helix_edge is not None and path_edge is None:
            # The native helix is a construction feature in some SolidWorks
            # versions. Once it has been replaced by the sampled 3D sketch,
            # select that sketch's actual geometric segment, not the sketch
            # container, so the sweep API receives a path entity.
            path_segments = self._sketch_segments(path_sketch)
        for use_path_segments in (False, True):
            if use_path_segments and not path_segments:
                continue
            self._clear_selection()
            if profile_sketch is None or not self._select_entity(profile_sketch, append=False, mark=1):
                raise RuntimeError(f'Could not select the sweep profile for {node_id}')
            if use_path_segments:
                for segment in path_segments:
                    if not self._select_entity(segment, append=True, mark=4):
                        raise RuntimeError(f'Could not select a sweep path segment for {node_id}')
                if len(path_segments) > 1:
                    self._group_sweep_path_selection()
            elif (path_edge or path_sketch) is None or not self._select_entity(
                path_edge or path_sketch, append=True, mark=4
            ):
                raise RuntimeError(f'Could not select the sweep path for {node_id}')
            selection_state = self._selection_state()
            attempt_states.append({
                'path_selection': 'segments' if use_path_segments else path_selection_kind,
                'segment_count': len(path_segments),
                'selections': selection_state,
            })

            def create_sweep_from_definition(
                twist_control, twist_angle=None
            ):
                definition = self.model.FeatureManager.CreateDefinition(
                    SW_FM_SWEEP
                )
                if definition is None:
                    return None
                definition.Profile = profile_sketch
                definition.Path = path_edge or path_sketch
                definition.TwistControlType = int(twist_control)
                definition.PathAlignmentType = 0
                definition.AlignWithEndFaces = False
                definition.Merge = False
                if twist_angle is not None:
                    # SetTwistAngle is a COM Sub (void), not a Boolean method.
                    definition.SetTwistAngle(float(twist_angle))
                return self.model.FeatureManager.CreateFeature(definition)

            attempts = (
                *(
                    (
                        (
                            'feature_data_normal_constant_twist',
                            lambda: create_sweep_from_definition(
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                frenet_helix_twist,
                            ),
                        ),
                        (
                            'feature_data_normal_constant_reverse_twist',
                            lambda: create_sweep_from_definition(
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                -frenet_helix_twist,
                            ),
                        ),
                        (
                            'feature_data_constant_twist',
                            lambda: create_sweep_from_definition(
                                8, frenet_helix_twist
                            ),
                        ),
                        (
                            'feature_data_constant_reverse_twist',
                            lambda: create_sweep_from_definition(
                                8, -frenet_helix_twist
                            ),
                        ),
                        (
                            'feature_data_follow_path',
                            lambda: create_sweep_from_definition(0),
                        ),
                        (
                            'feature_data_keep_normal_constant',
                            lambda: create_sweep_from_definition(1),
                        ),
                        (
                            'legacy_normal_constant_twist',
                            lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                                False, False,
                                SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                False, False, 0, 0, False,
                                0.0, 0.0, 0, 0,
                                False, False, True,
                                frenet_helix_twist,
                                True, False, 0.0, 0,
                            ),
                        ),
                    )
                    if frenet_helix_twist is not None
                    else ()
                ),
                # Graph operations are functional and create an independent body.
                # Asking SolidWorks to merge here makes the result depend on unrelated
                # intermediate bodies already present in the document.
                (
                    'legacy_follow_path_independent',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept4(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, False, False, True, 0, True, False, 0.0, 0),
                ),
                # Documented SolidWorks multi-path sweep settings retained as
                # compatibility fallbacks after the independent-body attempt.
                (
                    'legacy_follow_path_merge_scope',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept4(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, True, True, True, 0.0, True, False, 0.0, 0),
                ),
                (
                    'legacy_swept2_independent',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept2(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, False, False, True),
                ),
                (
                    'legacy_swept2_merge_scope',
                    lambda: self.model.FeatureManager.InsertProtrusionSwept2(False, False, 0, False, False, 0, 0, False, 0.0, 0.0, 0.0, 0, True, True, True),
                ),
            )
            for attempt_name, attempt in attempts:
                try:
                    candidate_feature = attempt()
                    if candidate_feature is not None:
                        candidate_body = self._capture_new_body(
                            before, candidate_feature
                        )
                        feature = candidate_feature
                        successful_sweep_body = candidate_body
                        successful_sweep_attempt = attempt_name
                        break
                except Exception as exc:
                    self.logs.append(f'sweep attempt failed for {node_id}: {exc}')
            if feature is None:
                try:
                    temp_body = self._create_swept_temp_body((
                        False, False, 0,
                        False, False, 0, 0,
                        False, 0.0, 0.0, 0,
                        0, 0.0, True,
                    ))
                    if temp_body is not None:
                        return self._create_feature_from_body(
                            temp_body, f'SimpleCAD_{node_id}_sweep'
                        )
                except Exception as exc:
                    self.logs.append(
                        f'temporary sweep body attempt failed for {node_id}: {exc}'
                    )
            if feature is not None:
                break
        if feature is None and helix_edge is not None:
            self.logs.append(
                f'native helix sweep failed for {node_id}; using a '
                'geometry-generated 3D B-spline path'
            )
            path_sketch = self._create_3d_path_sketch(
                self._sampled_helix_path(helix_edge),
                f'SimpleCADSketch_{node_id}_sampled_helix',
            )
            path_edge = None
            path_selection_kind = 'sampled_helix'
            path_segments = self._sketch_segments(path_sketch)
            for use_path_segments in (False, True):
                if use_path_segments and not path_segments:
                    continue
                self._clear_selection()
                if profile_sketch is None or not self._select_entity(profile_sketch, append=False, mark=1):
                    raise RuntimeError(f'Could not select the sweep profile for {node_id}')
                if use_path_segments:
                    for segment in path_segments:
                        if not self._select_entity(segment, append=True, mark=4):
                            raise RuntimeError(f'Could not select a sweep path segment for {node_id}')
                    if len(path_segments) > 1:
                        self._group_sweep_path_selection()
                elif not self._select_entity(path_sketch, append=True, mark=4):
                    raise RuntimeError(f'Could not select the sampled sweep path for {node_id}')
                selection_state = self._selection_state()
                attempt_states.append({
                    'path_selection': 'segments' if use_path_segments else path_selection_kind,
                    'segment_count': len(path_segments),
                    'selections': selection_state,
                })
                feature = None
                for attempt_name, attempt in (
                    *(
                        (
                            (
                                'sampled_normal_constant_twist',
                                lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                                    False, False,
                                    SW_TWIST_CONTROL_NORMAL_CONSTANT_TWIST,
                                    False, False, 0, 0, False,
                                    0.0, 0.0, 0, 0,
                                    False, False, True,
                                    frenet_helix_twist,
                                    True, False, 0.0, 0,
                                ),
                            ),
                        )
                        if frenet_helix_twist is not None
                        else ()
                    ),
                    (
                        'sampled_follow_path_independent',
                        lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                            False, False, 0, False, False, 0, 0, False,
                            0.0, 0.0, 0, 0, False, False, True, 0.0, True,
                            False, 0.0, 0,
                        ),
                    ),
                    (
                        'sampled_follow_path_merge_scope',
                        lambda: self.model.FeatureManager.InsertProtrusionSwept4(
                            False, False, 0, False, False, 0, 0, False,
                            0.0, 0.0, 0, 0, True, True, True, 0.0, True,
                            False, 0.0, 0,
                        ),
                    ),
                ):
                    try:
                        feature = attempt()
                        if feature is not None:
                            successful_sweep_attempt = attempt_name
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'sampled sweep attempt failed for {node_id}: {exc}'
                        )
                if feature is None:
                    try:
                        temp_body = self._create_swept_temp_body((
                            False, False, 0,
                            False, False, 0, 0,
                            False, 0.0, 0.0, 0,
                            0, 0.0, True,
                        ))
                        if temp_body is not None:
                            return self._create_feature_from_body(
                                temp_body, f'SimpleCAD_{node_id}_sweep'
                            )
                    except Exception as exc:
                        self.logs.append(
                            f'temporary sampled sweep body attempt failed for {node_id}: {exc}'
                        )
                if feature is not None:
                    break
        if feature is None:
            raise SimpleCADUnsupportedOpError(
                f'SolidWorks sweep feature creation failed; attempts={attempt_states!r}; '
                f'logs={self.logs[-3:]!r}'
            )
        body = successful_sweep_body or self._capture_new_body(before, feature)
        self.logs.append(f'sweep {node_id} created by {successful_sweep_attempt or "unknown"}')
        return body

    def _copy_temp_body(self, body):
        # Prefer the caller's resolved proxy. A same-name body enumerated from
        # the document can refer to a different feature after chained fillets;
        # use fresh-name/bbox candidates only as fallbacks.
        bodies = [body]
        expected_name = self._body_name(body)
        expected_bbox = self._box_from_entity(body)
        expected_size = _distance(expected_bbox['min'], expected_bbox['max'])
        fresh_bodies = self._solid_bodies()
        same_name = [
            candidate for candidate in fresh_bodies
            if self._body_name(candidate) == expected_name
        ]
        bodies.extend(
            candidate for candidate in same_name
            if candidate is not body
        )
        if not same_name and expected_size > 1.0e-12 and fresh_bodies:
            best_body = min(
                fresh_bodies,
                key=lambda candidate: _bbox_score(
                    self._box_from_entity(candidate), expected_bbox
                ),
            )
            best_score = _bbox_score(
                self._box_from_entity(best_body), expected_bbox
            )
            if best_score <= max(1.0e-7, expected_size * 1.0e-7):
                bodies.append(best_body)
        try:
            typed_body = win32com.client.CastTo(body, 'IBody2')
            if typed_body is not None:
                bodies.append(typed_body)
        except Exception:
            pass

        errors = []
        for candidate in bodies:
            calls = (
                ('Copy', lambda candidate=candidate: candidate.Copy()),
                ('ICopy', lambda candidate=candidate: candidate.ICopy()),
                ('Copy2', lambda candidate=candidate: candidate.Copy2(False)),
                (
                    'DISPID 19',
                    lambda candidate=candidate: candidate._oleobj_.InvokeTypes(
                        19,
                        0,
                        pythoncom.DISPATCH_METHOD,
                        (pythoncom.VT_DISPATCH, 0),
                        (),
                    ),
                ),
                (
                    'DISPID 31',
                    lambda candidate=candidate: candidate._oleobj_.InvokeTypes(
                        31,
                        0,
                        pythoncom.DISPATCH_METHOD,
                        (pythoncom.VT_DISPATCH, 0),
                        (),
                    ),
                ),
            )
            for call_name, call in calls:
                try:
                    copied = call()
                    if copied is not None:
                        try:
                            return win32com.client.Dispatch(copied)
                        except Exception:
                            return copied
                    errors.append(f'{call_name}: returned None')
                except Exception as exc:
                    errors.append(f'{call_name}: {exc}')
        fresh_state = [
            (self._body_name(candidate), self._box_from_entity(candidate))
            for candidate in fresh_bodies
        ]
        self.logs.append(
            f'body copy attempts failed: expected_name={expected_name!r} '
            f'expected_bbox={expected_bbox!r} fresh={fresh_state!r} '
            f'attempts={errors!r}'
        )
        raise RuntimeError(
            f'Could not copy SolidWorks body; expected_name={expected_name!r}; '
            f'expected_bbox={expected_bbox!r}; fresh={fresh_state!r}; '
            f'attempts={errors!r}'
        )

    def _create_feature_from_body(self, temp_body, name):
        before = self._body_names()
        expected_bbox = self._box_from_entity(temp_body)
        feature = None
        for call in (
            lambda: self.model.CreateFeatureFromBody3(temp_body, False, 0),
            lambda: self.model.CreateFeatureFromBody3(temp_body, True, 0),
            lambda: self.model.CreateFeatureFromBody2(temp_body, False, 0),
            lambda: self.model.CreateFeatureFromBody(temp_body),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception:
                pass
        if feature is None:
            raise RuntimeError('SolidWorks CreateFeatureFromBody failed')
        try:
            feature.Name = str(name)
        except Exception:
            pass
        return self._capture_new_body(
            before, feature, expected_bbox=expected_bbox
        )

    def _apply_transform_to_temp_body(self, temp_body, matrix_data):
        transform = None
        try:
            # The getter is a property under late binding and a method under
            # version-bound wrappers. CreateTransform uses the shared DISPID.
            math_utility = _maybe_call(self.sw.GetMathUtility)
            array_data = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                [float(value) for value in matrix_data],
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
        except Exception:
            transform = None
        if transform is None:
            raise RuntimeError('Could not create SolidWorks MathTransform')
        for call in (
            lambda: temp_body.ApplyTransform(transform),
            lambda: temp_body.Transform2(transform),
        ):
            try:
                result = call()
                if result is None or bool(result):
                    return temp_body
            except Exception:
                pass
        raise RuntimeError('Could not transform SolidWorks body')

    def _transform_body_feature(self, body, matrix_data, name):
        if _is_identity_matrix(matrix_data):
            before = self._body_names()
            expected_bbox = self._box_from_entity(body)
            self._clear_selection()
            if self._select_solid_body(body, append=False, mark=1):
                feature = None
                for call in (
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        0.0, 0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0,
                        True, 1,
                    ),
                ):
                    try:
                        feature = call()
                        if feature is not None:
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'native body-copy attempt failed for {name}: {exc}'
                        )
                self._clear_selection()
                if feature is not None:
                    try:
                        feature.Name = str(name)
                    except Exception:
                        pass
                    return self._capture_new_body(
                        before, feature, expected_bbox=expected_bbox
                    )
        # A pure translation can be represented by SolidWorks' native
        # Move/Copy Body feature. Prefer this live feature over the temporary
        # BRep/CreateFeatureFromBody fallback so upstream edits propagate
        # through translated leaves after the document is reopened.
        if _is_translation_matrix(matrix_data):
            before = self._body_names()
            expected_bbox = self._box_from_entity(body)
            self._clear_selection()
            if self._select_solid_body(body, append=False, mark=1):
                tx, ty, tz = (float(matrix_data[index]) for index in (9, 10, 11))
                canonical_delta = tuple(
                    value * M_TO_MM / MODEL_SCALE
                    for value in (tx, ty, tz)
                )
                if isinstance(expected_bbox, dict):
                    expected_bbox = {
                        key: tuple(
                            float(point[index]) + canonical_delta[index]
                            for index in range(3)
                        )
                        for key, point in expected_bbox.items()
                    }
                distance = math.sqrt(tx * tx + ty * ty + tz * tz)
                if distance <= 1.0e-15:
                    direction = (1.0, 0.0, 0.0)
                else:
                    direction = (
                        tx / distance, ty / distance, tz / distance
                    )
                native_feature = None
                for call in (
                    # SolidWorks' own Move Bodies example passes the XYZ
                    # displacement directly and leaves TransDist at zero.
                    # Graph transforms are functional and may feed multiple
                    # branches, so always copy the live input body here. A
                    # native move would consume it and force later branches
                    # onto static Body2 snapshots.
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        tx, ty, tz, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        tx, ty, tz, 0.0,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                        direction[0], direction[1], direction[2], distance,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                    lambda: self.model.FeatureManager.InsertMoveCopyBody(
                        direction[0], direction[1], direction[2], distance,
                        0.0, 0.0, 0.0,
                        0.0, 0.0, 0.0, True, 1,
                    ),
                ):
                    try:
                        native_feature = call()
                        if native_feature is not None:
                            break
                    except Exception as exc:
                        self.logs.append(
                            f'native translated body attempt failed for {name}: {exc}'
                        )
                self._clear_selection()
                if native_feature is not None:
                    try:
                        native_feature.Name = str(name)
                    except Exception:
                        pass
                    self.logs.append(f'{name} uses native Move/Copy Body translation')
                    return self._capture_new_body(
                        before, native_feature, expected_bbox=expected_bbox
                    )
                self.logs.append(
                    f'native Move/Copy Body returned no feature for {name}; '
                    f'selection={self._selection_state()!r}; '
                    'falling back to static transform'
                )
            else:
                self.logs.append(
                    f'native translated body selection failed for {name}; '
                    'falling back to static transform'
                )
        else:
            self.logs.append(
                f'{name} transform is not a pure translation; using static fallback'
            )
        temp_body = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(temp_body, matrix_data)
        self._mark_degraded(name, 'static_transform')
        return self._create_feature_from_body(temp_body, name)

    def _rotate_body_feature(self, body, axis, angle_degrees, origin, name):
        axis = _unit(axis)
        matrix_data = _rotation_matrix(axis, angle_degrees, origin)
        principal_index = None
        principal_sign = 1.0
        for index in range(3):
            if (
                abs(abs(axis[index]) - 1.0) <= 1.0e-10
                and all(abs(axis[other]) <= 1.0e-10 for other in range(3) if other != index)
            ):
                principal_index = index
                principal_sign = 1.0 if axis[index] >= 0.0 else -1.0
                break
        if principal_index is None:
            self.logs.append(
                f'{name} rotation axis is not principal; using static fallback'
            )
            return self._transform_body_feature(body, matrix_data, name)

        expected_probe = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(expected_probe, matrix_data)
        expected_bbox = self._box_from_entity(expected_probe)
        before = self._body_names()
        self._clear_selection()
        if self._select_solid_body(body, append=False, mark=1):
            rotation_point = _pt_m(origin)
            rotation_angles = [0.0, 0.0, 0.0]
            # The late-bound SolidWorks COM call exposes the three rotation
            # values in Z/Y/X axis order on this API version. A direct probe
            # with a non-symmetric body verifies that argument 0 rotates about
            # world Z and argument 2 about world X.
            rotation_angles[
                _solidworks_rotation_angle_index(principal_index)
            ] = (
                math.radians(float(angle_degrees)) * principal_sign
            )
            feature = None
            for call in (
                lambda: self.model.FeatureManager.InsertMoveCopyBody2(
                    0.0, 0.0, 0.0, 0.0,
                    rotation_point[0], rotation_point[1], rotation_point[2],
                    rotation_angles[0], rotation_angles[1], rotation_angles[2],
                    True, 1,
                ),
                lambda: self.model.FeatureManager.InsertMoveCopyBody(
                    0.0, 0.0, 0.0, 0.0,
                    rotation_point[0], rotation_point[1], rotation_point[2],
                    rotation_angles[0], rotation_angles[1], rotation_angles[2],
                    True, 1,
                ),
            ):
                try:
                    feature = call()
                    if feature is not None:
                        break
                except Exception as exc:
                    self.logs.append(
                        f'native rotated body attempt failed for {name}: {exc}'
                    )
            self._clear_selection()
            if feature is not None:
                try:
                    feature.Name = str(name)
                except Exception:
                    pass
                self.logs.append(f'{name} uses native Move/Copy Body rotation')
                return self._capture_new_body(
                    before, feature, expected_bbox=expected_bbox
                )
        self.logs.append(
            f'native Move/Copy Body rotation failed for {name}; '
            'using static fallback'
        )
        temp_body = self._copy_temp_body(body)
        self._apply_transform_to_temp_body(temp_body, matrix_data)
        self._mark_degraded(name, 'static_transform')
        return self._create_feature_from_body(temp_body, name)

    def _feature_shell(self, params, inputs, node_id):
        upstream = self._body_from_value(self._first_output(inputs[0]))
        # Keep shell attached to the live upstream body for the same reason as
        # fillet/chamfer: an identity Move/Copy snapshot breaks downstream
        # propagation when an earlier native feature is edited after reopen.
        source = upstream
        source_bbox = self._box_from_entity(source)
        selectors = []
        for selector_id in params.get('selected_face_node_ids') or []:
            payload = self.selection_payloads.get(str(selector_id))
            if payload:
                selectors.append(payload.get('params') or {})
        if not selectors:
            for item in params.get('selected_faces') or []:
                if isinstance(item, dict):
                    selectors.append(item.get('selector_hint') or item)
        face_signatures = [
            (face, self._face_signature(face))
            for face in self._body_faces(source)
        ]
        faces = [
            _best_by_geometry(face_signatures, selector, 'face')
            for selector in selectors
        ]
        self._clear_selection()
        for index, face in enumerate(faces):
            if not self._select_entity(face, append=index > 0):
                raise RuntimeError('Could not select SolidWorks face for shell')
        before = self._body_names()
        thickness = _as_m(params.get('thickness', 0.0))
        feature = None
        for call in (
            lambda: self.model.FeatureManager.InsertShell(thickness, False),
            lambda: self.model.FeatureManager.InsertShell2(thickness, False),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception as exc:
                self.logs.append(f'shell attempt failed for {node_id}: {exc}')
        if feature is None:
            raise RuntimeError('SolidWorks shell feature creation failed')
        return self._capture_new_body(
            before, feature, expected_bbox=source_bbox
        )

    def _features(self, type_names=None):
        wanted = set(type_names or [])
        features = []
        try:
            feature = _maybe_call(self.model.FirstFeature)
        except Exception:
            feature = None
        guard = 0
        while feature is not None and guard < 10000:
            guard += 1
            try:
                type_name = str(_maybe_call(feature.GetTypeName2))
            except Exception:
                type_name = ''
            if not wanted or type_name in wanted:
                features.append(feature)
            try:
                feature = _maybe_call(feature.GetNextFeature)
            except Exception:
                break
        return features

    def _feature_identity(self, feature):
        try:
            return str(feature.GetID())
        except Exception:
            pass
        try:
            return str(feature.Name)
        except Exception:
            return str(id(feature))


__all__ = ["FeatureRuntimeMixin"]
