"""SolidWorks runtime fragment: the composed automation runtime."""


class SimpleCADUnsupportedOpError(RuntimeError):
    pass


class SimpleCADSolidWorksRuntime(
    DocumentMetadataMixin,
    SelectionRuntimeMixin,
    SketchRuntimeMixin,
    FeatureRuntimeMixin,
    BooleanRuntimeMixin,
    BodyProductRuntimeMixin,
    AssemblyRuntimeMixin,
    PersistenceRuntimeMixin,
):
    def __init__(self, payload, document_name, result_node_ids, *, visible=True, solidworks_version='2025'):
        global MODEL_SCALE
        self.payload = payload
        self.graph = payload.get('graph') or {}
        self.nodes = self.graph.get('nodes') or []
        self.node_by_id = {str(node.get('node_id')): node for node in self.nodes}
        self.child_nodes = {}
        for child in self.nodes:
            for input_ref in child.get('inputs') or []:
                input_id = str(
                    input_ref.get('node_id')
                    if isinstance(input_ref, dict)
                    else input_ref
                )
                self.child_nodes.setdefault(input_id, []).append(child)
        self.detail_edge_catalog = {}
        encoded_detail_catalog = payload.get(
            'solidworks_detail_edge_catalog_z'
        )
        if isinstance(encoded_detail_catalog, str) and encoded_detail_catalog:
            try:
                decoded_detail_catalog = json.loads(
                    zlib.decompress(
                        base64.b64decode(encoded_detail_catalog.encode('ascii'))
                    ).decode('ascii')
                )
                if (
                    isinstance(decoded_detail_catalog, dict)
                    and decoded_detail_catalog.get('method') == 'gsm'
                ):
                    self.detail_edge_catalog = dict(
                        decoded_detail_catalog.get('sources') or {}
                    )
            except Exception:
                self.detail_edge_catalog = {}
        self.document_name = document_name
        self.result_node_ids = [str(v) for v in (result_node_ids or [])]
        self.outputs = {}
        self.product_values = {}
        self.selection_payloads = {}
        self.sketch_segments = {}
        self.materialized_source_body_keys = set()
        self.component_instance_counter = 0
        self.assembly_occurrences = []
        self.degraded_features = []
        self.persisted_topology_maps = {}
        self.captured_topology_source_ids = set()
        self.pending_detail_topology = []
        self.logs = []
        self.visible = bool(visible)
        self.solidworks_version = normalize_solidworks_version(solidworks_version)
        MODEL_SCALE = _model_work_scale(payload)
        self.logs.append(f'SolidWorks working geometry scale: {MODEL_SCALE:.9g}')

        self.sw = None
        self.model = None
        self._owns_solidworks = False
        self.actual_revision = None
        self.actual_type_library = None
        self.solidworks_pid = None
        self.solidworks_session_history = []
        try:
            self._start_solidworks()
            self.model = self._new_part()
            self._set_document_title(document_name)
            self._set_mmgs_units()
        except Exception:
            self._stop_solidworks()
            raise

    def _start_solidworks(self):
        """Create and verify an owned session, including after a native reopen."""
        if self.sw is not None:
            raise RuntimeError('A SolidWorks session is already attached to this runtime')
        self.sw = win32com.client.DispatchEx(_solidworks_progid(self.solidworks_version))
        self._owns_solidworks = True
        self.actual_revision = None
        self.actual_type_library = None
        self.solidworks_pid = None
        session = {
            'requested_version': self.solidworks_version,
            'pid': None,
            'revision': None,
        }
        self.solidworks_session_history.append(session)
        try:
            # Record the owned PID before any version/configuration failure so
            # an external runner can also clean up a stalled COM server.
            self.solidworks_pid = int(_maybe_call(self.sw.GetProcessID))
            session['pid'] = self.solidworks_pid
            self.actual_revision = str(_maybe_call(self.sw.RevisionNumber))
            session['revision'] = self.actual_revision
            _verify_solidworks_revision(self.solidworks_version, self.actual_revision)
            self.sw, self.actual_type_library = _bind_solidworks_dispatch(
                self.sw, self.solidworks_version
            )
            session['type_library'] = self.actual_type_library
            self.sw.Visible = self.visible
            try:
                self.sw.CommandInProgress = True
            except Exception:
                pass
            message = (
                'SIMPLECAD_SW_SESSION=%s'
                % json.dumps(session, sort_keys=True)
            )
            self.logs.append(message)
            print(message, flush=True)
            return self.sw
        except Exception:
            self._stop_solidworks()
            raise

    def _stop_solidworks(self):
        """Close only this runtime's isolated application, regardless of visibility."""
        sw = self.sw
        owned = self._owns_solidworks
        # Document proxies can be stale after a reopen or failed feature.
        # Release them without making calls such as GetTitle during cleanup.
        self.model = None
        self.sw = None
        self._owns_solidworks = False
        if sw is None or not owned:
            return
        try:
            sw.CommandInProgress = False
        except Exception:
            pass
        try:
            sw.CloseAllDocuments(True)
        except Exception:
            pass
        try:
            sw.ExitApp()
        except Exception:
            pass

    def _result_dependency_ids(self, result_node_ids):
        needed = set()
        pending = [str(node_id) for node_id in (result_node_ids or [])]
        while pending:
            node_id = pending.pop()
            if node_id in needed:
                continue
            node = self.node_by_id.get(node_id)
            if not isinstance(node, dict):
                continue
            needed.add(node_id)
            for ref in node.get('inputs') or []:
                if isinstance(ref, dict) and ref.get('node_id') is not None:
                    pending.append(str(ref.get('node_id')))
            params = node.get('params') or {}
            for key in ('selected_edge_node_ids', 'selected_face_node_ids'):
                pending.extend(str(value) for value in (params.get(key) or []))
        return needed

    def run(self, output_path=None):
        if not self.result_node_ids:
            self.result_node_ids = [str(node.get('node_id')) for node in self.nodes[-1:]]
        active_node_ids = self._result_dependency_ids(self.result_node_ids)
        processed = 0
        total = len(active_node_ids) or len(self.nodes)
        for node in self.nodes:
            if active_node_ids and str(node.get('node_id')) not in active_node_ids:
                continue
            if processed % 25 == 0:
                print(
                    f'SIMPLECAD_SW_PROGRESS={processed}/{total}:'
                    f'{node.get("node_id")}:{node.get("op")}',
                    flush=True,
                )
            node_started = time.perf_counter()
            try:
                self._emit_node(node)
            except Exception:
                raise
            node_elapsed = time.perf_counter() - node_started
            if node_elapsed >= 5.0:
                print(
                    f'SIMPLECAD_SW_SLOW_NODE={node.get("node_id")}:'
                    f'{node.get("op")}:{node_elapsed:.3f}',
                    flush=True,
                )
            processed += 1

        self.finalize(output_path=output_path)

    def finalize(self, output_path=None):
        if self.logs:
            print('\n'.join(self.logs), flush=True)
        final_bodies = self._result_bodies()
        if not final_bodies:
            raise RuntimeError('SolidWorks translator produced no final solid bodies')
        retained_source_bodies = [
            occurrence.get('source_body')
            for occurrence in self.assembly_occurrences
            if occurrence.get('source_body') is not None
        ]
        final_bodies = self._prune_to_bodies(
            final_bodies, retained_bodies=retained_source_bodies
        )
        final_bodies = self._restore_model_scale(
            final_bodies, retained_bodies=retained_source_bodies
        )
        if (
            self.assembly_occurrences
            and len(self.assembly_occurrences) == len(final_bodies)
        ):
            for occurrence, final_body in zip(
                self.assembly_occurrences, final_bodies
            ):
                occurrence['body'] = final_body
                occurrence['expected_bbox'] = self._box_from_entity(
                    final_body
                )
                # The unplaced source snapshot was captured when the terminal
                # part branch was materialized. By this point Keep Bodies may
                # have consumed both final and source Body2 proxies.
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        self._persist_document_metadata()
        if output_path:
            native_part_path = _native_part_output_path(output_path)
            self._save_native_part(native_part_path)
            if self.pending_detail_topology and not self.assembly_occurrences:
                self._reopen_native_part(native_part_path)
                self._retry_pending_detail_topology()
                self._persist_document_metadata()
                self._save_native_part(native_part_path)
            self._save_step(output_path)
            if self.assembly_occurrences:
                self._save_native_assembly(
                    output_path,
                    _native_assembly_output_path(output_path),
                )
        if self.logs:
            print('\n'.join(self.logs))

    def finish(self):
        self._stop_solidworks()
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass

    def emit_node(self, node):
        """Translate a graph node; operation failures must propagate."""
        return self._emit_node(node)

    def _input_ids(self, node):
        return [str(ref.get('node_id')) for ref in (node.get('inputs') or []) if isinstance(ref, dict)]

    def _is_terminal_part_feature(self, node_id):
        if str(node_id) in self.result_node_ids:
            return True
        children = self.child_nodes.get(str(node_id)) or []
        return bool(children) and all(
            str(child.get('op') or '') in {
                'make_part_rpart',
                'make_assign_material_rpart',
            }
            for child in children
        )

    def _mark_degraded(self, feature_name, reason):
        marker = {
            'feature': str(feature_name),
            'reason': str(reason),
        }
        if marker not in self.degraded_features:
            self.degraded_features.append(marker)
        self.logs.append(
            'SIMPLECAD_SW_DEGRADED=' + json.dumps(
                marker, ensure_ascii=True, sort_keys=True
            )
        )

    def _first_output(self, node_id):
        outputs = self.outputs.get(str(node_id)) or []
        if not outputs:
            raise RuntimeError(f'Missing graph output for {node_id}')
        return outputs[0]

    def _set_output(self, node, values):
        node_id = str(node.get('node_id'))
        if not isinstance(values, list):
            values = [values]
        for value in values:
            if not isinstance(value, dict):
                continue
            if value.get('kind') == 'compound':
                bodies = [
                    body for body in value.get('bodies') or []
                    if body is not None
                ]
                value.setdefault(
                    '_body_names', [self._body_name(body) for body in bodies]
                )
                value.setdefault(
                    '_body_bboxes', [
                        self._box_from_entity(body) for body in bodies
                    ],
                )
                continue
            if value.get('kind') != 'body':
                continue
            body = value.get('body')
            if body is None:
                continue
            value.setdefault('_body_name', self._body_name(body))
            value.setdefault('_body_bbox', self._box_from_entity(body))
            if '_body_snapshot' not in value:
                try:
                    value['_body_snapshot'] = self._copy_temp_body(body)
                except Exception as exc:
                    self.logs.append(
                        f'body snapshot failed for {node_id}: {exc}'
                    )
        self.outputs[node_id] = values
        return values

    def _emit_node(self, node):
        op = str(node.get('op'))
        params = node.get('params') or {}
        node_id = str(node.get('node_id'))
        inputs = self._input_ids(node)

        if op == 'make_interpolated_spline_redge':
            exact = params.get('_exact_bspline')
            if isinstance(exact, dict) and exact.get('control_points'):
                return self._set_output(node, {
                    'kind': 'edge',
                    'type': 'spline',
                    'controls': [_v3(point) for point in (exact.get('control_points') or [])],
                    'degree': int(exact.get('degree') or 3),
                    'knots': [float(value) for value in (exact.get('knots') or [])],
                    'multiplicities': [int(value) for value in (exact.get('multiplicities') or [])],
                    'weights': [float(value) for value in (exact.get('weights') or [])],
                    'periodic': bool(params.get('periodic', False)),
                })
            points = params.get('points') or []
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'spline',
                'controls': [_v3(point) for point in points],
                'periodic': bool(params.get('periodic', False)),
            })
        if op == 'make_box_rsolid':
            width = float(params.get('width', 0.0))
            height = float(params.get('height', 0.0))
            depth = float(params.get('depth', 0.0))
            center = _v3(params.get('bottom_face_center') or (0.0, 0.0, 0.0))
            x0, x1 = center[0] - width * 0.5, center[0] + width * 0.5
            y0, y1 = center[1] - height * 0.5, center[1] + height * 0.5
            z = center[2]
            points = [(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)]
            edges = [
                {'kind': 'edge', 'type': 'line', 'start': points[index], 'end': points[(index + 1) % 4]}
                for index in range(4)
            ]
            profile = {
                'kind': 'face',
                'outer': {'kind': 'wire', 'edges': edges},
                'inners': [],
                'normal': (0.0, 0.0, 1.0),
            }
            body = self._extrude_profile(
                profile, {'direction': (0.0, 0.0, 1.0), 'distance': depth}, node_id
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_cylinder_rsolid':
            center = _v3(params.get('bottom_face_center') or (0.0, 0.0, 0.0))
            axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
            radius = float(params.get('radius', 0.0))
            profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [{
                        'kind': 'edge',
                        'type': 'circle',
                        'center': center,
                        'radius': radius,
                        'normal': axis,
                    }],
                },
                'inners': [],
                'normal': axis,
            }
            body = self._extrude_profile(
                profile,
                {'direction': axis, 'distance': float(params.get('height', 0.0))},
                node_id,
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_cone_rsolid':
            bottom = _v3(params.get('bottom_face_center') or (0.0, 0.0, 0.0))
            axis = _unit(params.get('axis') or (0.0, 0.0, 1.0))
            top = _add(bottom, _mul(axis, float(params.get('height', 0.0))))
            radial, _unused = _plane_axes(axis)
            bottom_outer = _add(
                bottom, _mul(radial, float(params.get('bottom_radius', 0.0)))
            )
            top_outer = _add(
                top, _mul(radial, float(params.get('top_radius', 0.0)))
            )
            points = [bottom, bottom_outer, top_outer, top]
            compact_points = []
            for point in points:
                if not compact_points or _distance(point, compact_points[-1]) > 1.0e-12:
                    compact_points.append(point)
            edges = [
                {
                    'kind': 'edge',
                    'type': 'line',
                    'start': compact_points[index],
                    'end': compact_points[(index + 1) % len(compact_points)],
                }
                for index in range(len(compact_points))
            ]
            profile = {
                'kind': 'face',
                'outer': {'kind': 'wire', 'edges': edges},
                'inners': [],
                'normal': _unit(_cross(axis, radial)),
            }
            body = self._revolve_profile(
                profile, {'origin': bottom, 'axis': axis, 'angle': 360.0}, node_id
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_sphere_rsolid':
            center = _v3(params.get('center') or (0.0, 0.0, 0.0))
            radius = float(params.get('radius', 0.0))
            axis = (0.0, 0.0, 1.0)
            radial = (1.0, 0.0, 0.0)
            lower = _sub(center, _mul(axis, radius))
            outer = _add(center, _mul(radial, radius))
            upper = _add(center, _mul(axis, radius))
            profile = {
                'kind': 'face',
                'outer': {
                    'kind': 'wire',
                    'edges': [
                        {
                            'kind': 'edge',
                            'type': 'three_point_arc',
                            'start': lower,
                            'middle': outer,
                            'end': upper,
                        },
                        {'kind': 'edge', 'type': 'line', 'start': upper, 'end': lower},
                    ],
                },
                'inners': [],
                'normal': (0.0, 1.0, 0.0),
            }
            body = self._revolve_profile(
                profile, {'origin': center, 'axis': axis, 'angle': 360.0}, node_id
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'apply_tag_rselection':
            value = self._first_output(inputs[0])
            if isinstance(value, dict):
                value = dict(value)
                value.setdefault('tag_bindings', []).append(
                    dict(params.get('tag_binding') or {})
                )
            return self._set_output(node, value)
        if op == 'make_line_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'line', 'start': _v3(params.get('start')), 'end': _v3(params.get('end'))})
        if op == 'make_circle_redge':
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'circle',
                'center': _v3(params.get('center')),
                'radius': float(params.get('radius', 1.0)),
                'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0)),
                '_kernel_x_axis': params.get('_kernel_x_axis'),
                '_kernel_y_axis': params.get('_kernel_y_axis'),
            })
        if op == 'make_angle_arc_redge':
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'angle_arc',
                'center': _v3(params.get('center')),
                'radius': float(params.get('radius', 1.0)),
                'start_angle': float(params.get('start_angle', 0.0)),
                'end_angle': float(params.get('end_angle', 0.0)),
                'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0)),
                '_kernel_x_axis': params.get('_kernel_x_axis'),
                '_kernel_y_axis': params.get('_kernel_y_axis'),
            })
        if op == 'make_three_point_arc_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'three_point_arc', 'start': _v3(params.get('start')), 'middle': _v3(params.get('middle')), 'end': _v3(params.get('end'))})
        if op == 'make_spline_redge':
            controls = params.get('control_points') or params.get('controls') or params.get('points') or []
            return self._set_output(node, {
                'kind': 'edge',
                'type': 'spline',
                'controls': [_v3(point) for point in controls],
                'degree': int(params.get('degree') or min(3, max(1, len(controls) - 1))),
                'knots': [float(value) for value in (params.get('knots') or [])],
                'multiplicities': [int(value) for value in (params.get('multiplicities') or [])],
                'weights': [float(value) for value in (params.get('weights') or [])],
                'periodic': bool(params.get('periodic', False)),
            })
        if op == 'make_helix_redge':
            return self._set_output(node, {'kind': 'edge', 'type': 'helix', 'params': dict(params)})
        if op == 'make_wire_from_edges_rwire':
            edges = []
            for input_id in inputs:
                value = self._first_output(input_id)
                if isinstance(value, dict) and value.get('kind') == 'wire':
                    edges.extend(value.get('edges') or [])
                else:
                    edges.append(value)
            return self._set_output(node, {'kind': 'wire', 'edges': edges})
        if op == 'make_face_from_wire_rface':
            return self._set_output(node, {'kind': 'face', 'outer': self._first_output(inputs[0]), 'inners': [], 'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0))})
        if op == 'make_face_from_wires_rface':
            wires = [self._first_output(input_id) for input_id in inputs]
            if not wires:
                raise RuntimeError('make_face_from_wires_rface requires wire inputs')
            return self._set_output(node, {'kind': 'face', 'outer': wires[0], 'inners': wires[1:], 'normal': _unit(params.get('normal') or (0.0, 0.0, 1.0))})
        if op in {'make_wire_from_sketch_rwire', 'make_face_from_sketch_rface'}:
            raise SimpleCADUnsupportedOpError(f'{op} is not yet supported by the SolidWorks translator')
        if op == 'make_extrude_rsolid':
            body = self._extrude_profile(self._first_output(inputs[0]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_revolve_rsolid':
            body = self._revolve_profile(self._first_output(inputs[0]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_loft_rsolid':
            body = self._loft_profiles([self._first_output(input_id) for input_id in inputs], params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_sweep_rsolid':
            body = self._sweep_profile(self._first_output(inputs[0]), self._first_output(inputs[1]), params, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_cut_rsolid':
            bases = self._bodies_from_value(self._first_output(inputs[0]))
            tools = []
            for input_id in inputs[1:]:
                tools.extend(
                    self._bodies_from_value(self._first_output(input_id))
                )
            if len(bases) > 1:
                # A disjoint Union is a live body set, not a failed single-body
                # union. Apply the shared cutters independently to each target
                # section. A cutter may belong to at most one section here;
                # otherwise SolidWorks would consume the same live tool twice.
                tool_owners = []
                for tool in tools:
                    owners = [
                        index for index, base in enumerate(bases)
                        if self._body_intersection_has_volume(base, tool)
                    ]
                    tool_owners.append(owners)
                cut_bodies = []
                for base_index, base in enumerate(bases):
                    section_tools = [
                        tool for tool, owners in zip(tools, tool_owners)
                        if base_index in owners
                    ]
                    section_result = self._boolean_body(
                        base,
                        section_tools,
                        SWBODYCUT,
                        f'SimpleCAD_{node_id}_section_{base_index + 1}',
                        # Bbox-disjoint tools are exact no-ops for this section.
                        skip_non_intersecting=True,
                        allow_split_sections=True,
                        prefer_native=True,
                    )
                    if isinstance(section_result, list):
                        cut_bodies.extend(section_result)
                    else:
                        cut_bodies.append(section_result)
                self.logs.append(
                    f'cut SimpleCAD_{node_id} preserved '
                    f'{len(cut_bodies)} live result sections'
                )
                if len(cut_bodies) > 1:
                    return self._set_output(
                        node, {'kind': 'compound', 'bodies': cut_bodies}
                    )
                return self._set_output(
                    node, {'kind': 'body', 'body': cut_bodies[0]}
                )
            body = self._boolean_body(
                bases[0],
                tools,
                SWBODYCUT,
                f'SimpleCAD_{node_id}',
                skip_non_intersecting=bool(params.get('skip_non_intersecting', False)),
                # Keep the edited base live even when this Cut is followed by
                # another graph node; static boolean copies sever propagation.
                prefer_native=True,
            )
            if isinstance(body, list):
                return self._set_output(node, {'kind': 'compound', 'bodies': body})
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_union_rsolid':
            input_body_sets = [
                self._bodies_from_value(self._first_output(input_id))
                for input_id in inputs
            ]
            bodies = [
                body for body_set in input_body_sets for body in body_set
            ]
            if not bodies:
                raise RuntimeError(f'Union SimpleCAD_{node_id} has no bodies')
            unseen = set(range(len(bodies)))
            components = []
            while unseen:
                start = min(unseen)
                unseen.remove(start)
                pending = [start]
                component = []
                while pending:
                    current = pending.pop()
                    component.append(current)
                    neighbors = [
                        candidate for candidate in sorted(unseen)
                        if self._body_union_is_single(
                            bodies[current], bodies[candidate]
                        )
                    ]
                    for candidate in neighbors:
                        unseen.remove(candidate)
                        pending.append(candidate)
                components.append(sorted(component))
            if len(components) > 1:
                # Disconnected components cannot intersect. Combine
                # only within each connected group, then preserve the
                # exact union as a live body set across the groups.
                component_body_sets = []
                for component_index, component in enumerate(components):
                    component_bodies = [bodies[index] for index in component]
                    if len(component_bodies) == 1:
                        component_result = component_bodies[0]
                    else:
                        component_result = self._boolean_body(
                            component_bodies[0],
                            component_bodies[1:],
                            SWBODYADD,
                            f'SimpleCAD_{node_id}_component_'
                            f'{component_index + 1}',
                            clean=bool(params.get('clean', False)),
                            prefer_native=True,
                        )
                    component_body_sets.append(
                        list(component_result)
                        if isinstance(component_result, list)
                        else [component_result]
                    )
                body = [
                    candidate
                    for body_set in component_body_sets
                    for candidate in body_set
                ]
                self.logs.append(
                    f'union SimpleCAD_{node_id} preserved '
                    f'{len(body)} disconnected live components '
                    f'from {len(bodies)} input bodies'
                )
            else:
                body = self._boolean_body(
                    bodies[0],
                    bodies[1:],
                    SWBODYADD,
                    f'SimpleCAD_{node_id}',
                    clean=bool(params.get('clean', False)),
                    prefer_native=True,
                )
            if isinstance(body, list):
                if len(body) == 1:
                    return self._set_output(
                        node, {'kind': 'body', 'body': body[0]}
                    )
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_intersect_rsolid':
            bodies = [self._body_from_value(self._first_output(input_id)) for input_id in inputs]
            body = self._boolean_body(
                bodies[0],
                bodies[1:],
                SWBODYINTERSECT,
                f'SimpleCAD_{node_id}',
                prefer_native=True,
            )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_select_redge':
            payload = {'kind': 'edge', 'params': params, 'input': inputs[0] if inputs else None}
            self.selection_payloads[node_id] = payload
            if os.environ.get('SIMPLECAD_SW_TRACE_SELECTIONS') == '1' and inputs:
                try:
                    source = self._body_from_value(self._first_output(inputs[0]))
                    selector = params.get('geo_selector') or params
                    signatures = [
                        self._edge_signature(edge)
                        for edge in self._body_edges(source)
                    ]
                    ranked = sorted(
                        signatures,
                        key=lambda signature: _geom_score(signature, selector),
                    )
                    trace = {
                        'node_id': node_id,
                        'source_id': inputs[0],
                        'best_score': (
                            _geom_score(ranked[0], selector)
                            if ranked else None
                        ),
                        'type_mismatch': (
                            _geom_type_mismatch(ranked[0], selector)
                            if ranked else None
                        ),
                        'selector': _selector_geometry(selector),
                        'best': ranked[0] if ranked else None,
                    }
                    print(
                        'SIMPLECAD_SW_SELECTION=' + json.dumps(
                            trace, ensure_ascii=True, sort_keys=True
                        ),
                        flush=True,
                    )
                except Exception as exc:
                    print(
                        f'SIMPLECAD_SW_SELECTION_ERROR={node_id}:{exc}',
                        flush=True,
                    )
            return self._set_output(node, payload)
        if op == 'make_select_rface':
            payload = {'kind': 'face', 'params': params, 'input': inputs[0] if inputs else None}
            self.selection_payloads[node_id] = payload
            return self._set_output(node, payload)
        if op == 'make_fillet_rsolid':
            body = self._feature_detail_edges(params, inputs, 'fillet', node_id)
            if isinstance(body, list):
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_chamfer_rsolid':
            body = self._feature_detail_edges(params, inputs, 'chamfer', node_id)
            if isinstance(body, list):
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': body}
                )
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_shell_rsolid':
            body = self._feature_shell(params, inputs, node_id)
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_translate_rshape':
            value = self._first_output(inputs[0])
            vector = _v3(params.get('vector') or (0.0, 0.0, 0.0))
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _add(_v3(point), vector),
                    lambda direction: _v3(direction),
                )
                return self._set_output(node, transformed)
            bodies = [
                self._transform_body_feature(
                    body,
                    _translation_matrix(vector),
                    f'SimpleCAD_{node_id}_{index + 1}',
                )
                for index, body in enumerate(self._bodies_from_value(value))
            ]
            if len(bodies) > 1:
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': bodies}
                )
            return self._set_output(node, {'kind': 'body', 'body': bodies[0]})
        if op == 'make_rotate_rshape':
            value = self._first_output(inputs[0])
            axis = params.get('axis') or (0.0, 0.0, 1.0)
            angle = params.get('angle', 0.0)
            origin = params.get('origin') or (0.0, 0.0, 0.0)
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _rotate_point_payload(point, axis, angle, origin),
                    lambda direction: _rotate_direction_payload(direction, axis, angle),
                )
                return self._set_output(node, transformed)
            bodies = [
                self._rotate_body_feature(
                    body,
                    axis,
                    angle,
                    origin,
                    f'SimpleCAD_{node_id}_{index + 1}',
                )
                for index, body in enumerate(self._bodies_from_value(value))
            ]
            if len(bodies) > 1:
                return self._set_output(
                    node, {'kind': 'compound', 'bodies': bodies}
                )
            return self._set_output(node, {'kind': 'body', 'body': bodies[0]})
        if op == 'make_mirror_rshape':
            value = self._first_output(inputs[0])
            plane_origin = params.get('plane_origin') or (0.0, 0.0, 0.0)
            plane_normal = params.get('plane_normal') or (0.0, 0.0, 1.0)
            if isinstance(value, dict) and value.get('kind') in {'edge', 'wire', 'face'}:
                transformed = _transform_geometry_value(
                    value,
                    lambda point: _mirror_point_payload(point, plane_origin, plane_normal),
                    lambda direction: _mirror_direction_payload(direction, plane_normal),
                )
                return self._set_output(node, transformed)
            body = self._transform_body_feature(self._body_from_value(value), _mirror_matrix(plane_origin, plane_normal), f'SimpleCAD_{node_id}')
            return self._set_output(node, {'kind': 'body', 'body': body})
        if op == 'make_material_rmaterial':
            return self._set_output(node, {'kind': 'material', 'params': params})
        if op in {'make_placement_rplacement', 'make_identity_placement_rplacement'}:
            return self._set_output(node, {'kind': 'placement', 'params': params})
        if op == 'make_part_rpart':
            value = {'kind': 'part', 'params': params, 'body_node': inputs[0], 'body': self._first_output(inputs[0])}
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_assign_material_rpart':
            value = dict(self._first_output(inputs[0]))
            value['material'] = self._first_output(inputs[1])
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_assembly_rassembly':
            value = {'kind': 'assembly', 'params': params, 'components': []}
            self.product_values[node_id] = value
            return self._set_output(node, value)
        if op == 'make_add_component_rassembly':
            assembly = dict(self._first_output(inputs[0]))
            components = list(assembly.get('components') or [])
            components.append({
                'component_id': str(params.get('component_id') or ''),
                'item': self._first_output(inputs[1]),
                'placement': self._first_output(inputs[2]) if len(inputs) > 2 else {'kind': 'placement', 'params': {}},
                'params': params,
            })
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_place_component_rassembly':
            assembly = dict(self._first_output(inputs[0]))
            placement = self._first_output(inputs[1])
            component_id = str(params.get('component_id') or '')
            components = []
            for component in assembly.get('components') or []:
                component = dict(component)
                if str(component.get('component_id') or '') == component_id:
                    component['placement'] = placement
                components.append(component)
            assembly['components'] = components
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_solve_assembly_constraints_rassembly':
            assembly = self._assembly_with_placements(
                self._first_output(inputs[0]),
                dict(params.get('component_placements') or {}),
            )
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'evaluate_assembly_definition':
            placements = {}
            for record in params.get('component_placements') or []:
                component_id = str(record['instance_id'])
                if component_id in placements:
                    raise RuntimeError(f'Duplicate solved component: {component_id}')
                placements[component_id] = record['placement']
            assembly = self._assembly_with_placements(self._first_output(inputs[0]), placements)
            assembly['constraint_report'] = dict(params.get('constraint_report') or {})
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_set_public_connector_rassembly':
            assembly = self._assembly_with_public_connector(self._first_output(inputs[0]), params)
            self.product_values[node_id] = assembly
            return self._set_output(node, assembly)
        if op == 'make_compound_from_assembly_rcompound':
            bodies = self._materialize_product_bodies(
                self._first_output(inputs[0]),
                f'SimpleCAD_{node_id}_component',
            )
            if not bodies:
                raise RuntimeError('assembly compound has no bodies')
            return self._set_output(node, {'kind': 'compound', 'bodies': bodies})
        if op.startswith('make_') and op.endswith('_rconnector'):
            return self._set_output(node, {'kind': 'connector', 'params': params})
        if op == 'make_add_connector_rpart':
            part = dict(self._first_output(inputs[0]))
            part['connectors'] = list(part.get('connectors') or []) + [self._first_output(inputs[1])]
            self.product_values[node_id] = part
            return self._set_output(node, part)
        if op in {
            'make_connector_ref_rconnectorref', 'make_scalar_limit_rscalarlimit',
            'make_ground_component_rassembly', 'make_unground_component_rassembly',
            'make_fixed_constraint_rassembly', 'make_revolute_constraint_rassembly',
            'make_prismatic_constraint_rassembly',
        }:
            value = self._first_output(inputs[0]) if inputs else {'kind': op, 'params': params}
            return self._set_output(node, value)
        raise SimpleCADUnsupportedOpError(f'Unsupported SimpleCAD op for SolidWorks translation: {op}')
