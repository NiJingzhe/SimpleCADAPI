"""SolidWorks runtime fragment: SketchRuntimeMixin."""


class SketchRuntimeMixin:
    def _sketch_segments(self, sketch_feature):
        feature_id = self._feature_identity(sketch_feature)
        registered = self.sketch_segments.get(feature_id)
        if registered:
            return list(registered)
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            segments = _maybe_call(sketch.GetSketchSegments)
        except Exception:
            segments = None
        if not segments:
            return []
        return list(segments) if isinstance(segments, (list, tuple)) else [segments]

    def _sketch_contours(self, sketch_feature):
        """Return sketch contours without depending on their returned order."""
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            contours = _maybe_call(sketch.GetSketchContours)
        except Exception:
            contours = None
        if not contours:
            return []
        return list(contours) if isinstance(contours, (list, tuple)) else [contours]

    def _sketch_regions(self, sketch_feature):
        sketch = None
        for getter_name in ('GetSpecificFeature2', 'GetSpecificFeature'):
            try:
                sketch = _maybe_call(getattr(sketch_feature, getter_name))
                if sketch is not None:
                    break
            except Exception:
                sketch = None
        if sketch is None:
            return []
        try:
            regions = _maybe_call(sketch.GetSketchRegions)
        except Exception:
            regions = None
        if not regions:
            return []
        return list(regions) if isinstance(regions, (list, tuple)) else [regions]

    def _sketch_segment_endpoint_gaps(self, sketch_feature):
        def point_coords(segment, getter_names):
            for getter_name in getter_names:
                try:
                    point = _maybe_call(getattr(segment, getter_name))
                except Exception:
                    continue
                if point is None:
                    continue
                if isinstance(point, (list, tuple)) and len(point) >= 3:
                    return tuple(float(value) for value in point[:3])
                try:
                    return (float(point.X), float(point.Y), float(point.Z))
                except Exception:
                    pass
            return None

        endpoints = []
        for segment in self._sketch_segments(sketch_feature):
            endpoints.append((
                point_coords(segment, ('GetStartPoint2', 'GetStartPoint')),
                point_coords(segment, ('GetEndPoint2', 'GetEndPoint')),
            ))
        gaps = []
        if endpoints:
            for index, (_start, end) in enumerate(endpoints):
                next_start = endpoints[(index + 1) % len(endpoints)][0]
                gap = None
                if end is not None and next_start is not None:
                    gap = _distance(end, next_start)
                gaps.append({
                    'after': index,
                    'end': end,
                    'next_start': next_start,
                    'gap_m': gap,
                })
        return gaps

    def _reference_plane_normal(self, feature):
        try:
            ref_plane = _maybe_call(feature.GetSpecificFeature2)
            transform = ref_plane.Transform
            data = tuple(float(value) for value in transform.ArrayData)
            if len(data) >= 9:
                return _unit((data[6], data[7], data[8]))
        except Exception:
            pass
        return None

    def _select_plane(self, axis):
        axis = _unit(axis)
        abs_axis = [abs(axis[0]), abs(axis[1]), abs(axis[2])]
        dominant = abs_axis.index(max(abs_axis))
        self._clear_selection()
        planes = []
        for index, feature in enumerate(self._features({'RefPlane'})):
            normal = self._reference_plane_normal(feature)
            score = 1.0e9
            if normal is not None:
                score = 1.0 - abs(_dot(normal, axis))
            elif index == {2: 0, 1: 1, 0: 2}.get(dominant, 0):
                score = 0.0
            planes.append((score, index, feature))
        for _score, _index, feature in sorted(planes, key=lambda item: (item[0], item[1])):
            try:
                if feature.Select2(False, 0):
                    if os.environ.get('SIMPLECAD_SW_TRACE_SKETCHES') == '1':
                        try:
                            _n = _maybe_call(getattr(feature, 'Name'))
                        except Exception:
                            _n = '?'
                        self.logs.append(
                            f'PLANE_TRACE _select_plane picked {_n!r} '
                            f'(score={_score:.3f}, idx={_index})'
                        )
                    selected_normal = self._reference_plane_normal(feature)
                    if selected_normal is None:
                        selected_normal = tuple(
                            1.0 if index == dominant else 0.0
                            for index in range(3)
                        )
                    return dominant, selected_normal
            except Exception:
                pass
        # Standard part planes can remain selectable by name even when the
        # feature-tree COM enumerator is temporarily stale.
        named_planes = (
            ('Front Plane', (0.0, 0.0, 1.0)),
            ('Top Plane', (0.0, 1.0, 0.0)),
            ('Right Plane', (1.0, 0.0, 0.0)),
        )
        for _name, normal in sorted(
            named_planes,
            key=lambda item: 1.0 - abs(_dot(item[1], axis)),
        ):
            try:
                if self.model.Extension.SelectByID2(
                    _name, 'PLANE', 0.0, 0.0, 0.0,
                    False, 0, _empty_dispatch(), 0,
                ):
                    return dominant, normal
            except Exception:
                pass
        raise RuntimeError('Could not select a SolidWorks base plane')

    def _select_profile_plane(self, axis, offset):
        dominant, base_normal = self._select_plane(axis)
        if abs(float(offset)) <= 1.0e-9:
            return dominant, base_normal
        before = {
            self._feature_identity(feature)
            for feature in self._features({'RefPlane'})
        }
        constraint = 8 | (256 if float(offset) < 0.0 else 0)
        ref_plane = self.model.FeatureManager.InsertRefPlane(
            constraint,
            _as_m(abs(float(offset))),
            0,
            0.0,
            0,
            0.0,
        )
        if ref_plane is None:
            raise RuntimeError('SolidWorks did not create the profile offset plane')
        self._clear_selection()
        new_planes = [
            feature
            for feature in self._features({'RefPlane'})
            if self._feature_identity(feature) not in before
        ]
        selected = False
        selected_normal = None
        for plane in reversed(new_planes):
            if self._select_entity(plane, append=False):
                selected = True
                selected_normal = self._reference_plane_normal(plane)
                break
        if not selected:
            selected = self._select_entity(ref_plane, append=False)
            selected_normal = self._reference_plane_normal(ref_plane)
        if not selected:
            raise RuntimeError('Could not select the generated profile offset plane')
        return dominant, selected_normal or base_normal

    def _profile_edges(self, profile):
        if isinstance(profile, dict) and profile.get('kind') == 'face':
            edges = []
            outer = profile.get('outer') or {}
            edges.extend(outer.get('edges') or [])
            for inner in profile.get('inners') or []:
                edges.extend(inner.get('edges') or [])
            return edges
        if isinstance(profile, dict) and profile.get('kind') == 'wire':
            return profile.get('edges') or []
        if isinstance(profile, dict) and profile.get('kind') == 'edge':
            return [profile]
        raise RuntimeError('Expected a SimpleCAD profile edge/wire/face payload')

    def _profile_normal(self, profile, fallback=(0.0, 0.0, 1.0)):
        hint = fallback
        if isinstance(profile, dict) and isinstance(profile.get('normal'), (list, tuple)):
            hint = profile.get('normal')
        points = self._profile_points(profile)
        if len(points) >= 3:
            origin = points[0]
            axis_point = max(points[1:], key=lambda point: _distance(point, origin))
            axis = _sub(axis_point, origin)
            normal_point = max(
                points[1:],
                key=lambda point: _norm(_cross(axis, _sub(point, origin))),
            )
            normal = _cross(axis, _sub(normal_point, origin))
            if _norm(normal) > 1.0e-9:
                normal = _unit(normal, hint)
                if _dot(normal, _unit(hint)) < 0.0:
                    normal = _mul(normal, -1.0)
                return normal
        for edge in self._profile_edges(profile):
            if edge.get('type') in {'circle', 'angle_arc'}:
                return _unit(edge.get('normal') or hint, hint)
        return _unit(hint)

    def _profile_points(self, profile):
        points = []
        for edge in self._profile_edges(profile):
            for value in self._edge_points_payload(edge):
                if not isinstance(value, (list, tuple)) or len(value) != 3:
                    continue
                point = _v3(value)
                if not any(_distance(point, existing) <= 1.0e-9 for existing in points):
                    points.append(point)
        return points

    def _profile_frame(self, profile, normal_hint):
        points = self._profile_points(profile)
        if len(points) < 3:
            raise RuntimeError('A planar SolidWorks profile requires at least three geometric points')
        origin = points[0]
        axis_point = max(points[1:], key=lambda point: _distance(point, origin))
        axis_vector = _sub(axis_point, origin)
        span = _norm(axis_vector)
        if span <= 1.0e-9:
            raise RuntimeError('SolidWorks profile plane has no stable geometric span')
        normal = self._profile_normal(profile, normal_hint)
        x_axis = _sub(axis_vector, _mul(normal, _dot(axis_vector, normal)))
        if _norm(x_axis) <= 1.0e-9:
            x_axis, _unused = _plane_axes(normal)
        else:
            x_axis = _unit(x_axis)
        y_axis = _unit(_cross(normal, x_axis))
        max_plane_error = max(abs(_dot(_sub(point, origin), normal)) for point in points)
        tolerance = max(1.0e-7, span * 1.0e-7)
        if max_plane_error > tolerance:
            raise RuntimeError(
                f'SolidWorks profile is not planar; geometric deviation={max_plane_error}'
            )
        return origin, x_axis, y_axis, normal, span

    def _edge_points_payload(self, edge):
        edge_type = edge.get('type')
        if edge_type == 'line':
            return [edge.get('start'), edge.get('end')]
        if edge_type == 'circle':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            x_axis = edge.get('_kernel_x_axis')
            y_axis = edge.get('_kernel_y_axis')
            if x_axis is None or y_axis is None:
                x_axis, y_axis = _plane_axes(
                    edge.get('normal') or (0.0, 0.0, 1.0)
                )
            else:
                x_axis = _unit(x_axis)
                y_axis = _unit(y_axis)
            return [
                center,
                _add(center, _mul(x_axis, radius)),
                _add(center, _mul(y_axis, radius)),
            ]
        if edge_type == 'angle_arc':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            start_angle = float(edge.get('start_angle', 0.0))
            end_angle = float(edge.get('end_angle', 0.0))
            normal = edge.get('normal') or (0.0, 0.0, 1.0)
            return [
                center,
                _angle_arc_world_point(
                    center,
                    radius,
                    start_angle,
                    normal,
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                ),
                _angle_arc_world_point(
                    center,
                    radius,
                    end_angle,
                    normal,
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                ),
            ]
        if edge_type == 'three_point_arc':
            return [edge.get('start'), edge.get('middle'), edge.get('end')]
        if edge_type == 'spline':
            return list(edge.get('controls') or [])
        return []

    def _plane_mapping(self, axis, profile=None):
        normal = _unit(axis)
        abs_axis = [abs(normal[0]), abs(normal[1]), abs(normal[2])]
        dominant = abs_axis.index(max(abs_axis))
        points = []
        if profile is not None:
            for edge in self._profile_edges(profile):
                points.extend(self._edge_points_payload(edge))
        if dominant == 2:
            offset = points[0][2] if points else 0.0
            return dominant, normal, offset, lambda p: (float(p[0]), float(p[1]))
        if dominant == 1:
            offset = points[0][1] if points else 0.0
            return dominant, normal, offset, lambda p: (float(p[0]), -float(p[2]))
        offset = points[0][0] if points else 0.0
        return dominant, normal, offset, lambda p: (-float(p[2]), float(p[1]))

    def _select_fixed_profile_plane(self, profile, normal_hint):
        origin, x_axis, y_axis, normal, span = self._profile_frame(profile, normal_hint)
        point_x = _add(origin, _mul(x_axis, span))
        point_y = _add(origin, _mul(y_axis, span))

        def point_variant(point):
            return win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                list(_pt_m(point)),
            )

        self._clear_selection()
        ref_plane = self.model.CreatePlaneFixed2(
            point_variant(origin),
            point_variant(point_x),
            point_variant(point_y),
            False,
        )
        if ref_plane is None:
            raise RuntimeError('SolidWorks did not create the geometry-defined profile plane')
        if not self._select_entity(ref_plane, append=False):
            raise RuntimeError('Could not select the geometry-defined SolidWorks profile plane')

        def mapper(point):
            relative = _sub(_v3(point), origin)
            return _dot(relative, x_axis), _dot(relative, y_axis)

        return normal, mapper

    def _ellipse_geometry_from_spline(self, edge, mapper):
        controls = list(edge.get('controls') or [])
        weights = list(edge.get('weights') or [])
        knots = [float(value) for value in (edge.get('knots') or [])]
        multiplicities = [int(value) for value in (edge.get('multiplicities') or [])]
        if (
            int(edge.get('degree', 3)) != 2
            or bool(edge.get('periodic'))
            or len(controls) != 9
            or len(weights) != 9
            or len(knots) != 5
            or knots[-1] <= knots[0]
            or any(abs((value - knots[0]) / (knots[-1] - knots[0]) - index / 4.0) > 1e-10 for index, value in enumerate(knots))
            or multiplicities != [3, 2, 2, 2, 3]
        ):
            return None
        corner_weight = math.sqrt(0.5)
        for index, weight in enumerate(weights):
            expected = 1.0 if index % 2 == 0 else corner_weight
            if abs(float(weight) - expected) > 1.0e-9:
                return None

        points = [tuple(float(value) for value in mapper(_v3(point))) for point in controls]

        def add2(first, second):
            return (first[0] + second[0], first[1] + second[1])

        def sub2(first, second):
            return (first[0] - second[0], first[1] - second[1])

        def mul2(point, scalar):
            return (point[0] * scalar, point[1] * scalar)

        def distance2(first, second):
            delta = sub2(first, second)
            return math.hypot(delta[0], delta[1])

        center_a = mul2(add2(points[0], points[4]), 0.5)
        center_b = mul2(add2(points[2], points[6]), 0.5)
        scale = max(
            1.0,
            max(distance2(point, center_a) for point in points),
        )
        tolerance = max(1.0e-8, scale * 1.0e-8)
        if distance2(points[0], points[8]) > tolerance:
            return None
        if distance2(center_a, center_b) > tolerance:
            return None
        center = mul2(add2(center_a, center_b), 0.5)
        first_axis = sub2(points[0], center)
        second_axis = sub2(points[2], center)
        first_radius = math.hypot(first_axis[0], first_axis[1])
        second_radius = math.hypot(second_axis[0], second_axis[1])
        if first_radius <= tolerance or second_radius <= tolerance:
            return None
        if abs(first_axis[0] * second_axis[0] + first_axis[1] * second_axis[1]) > tolerance * scale:
            return None
        expected_corners = (
            add2(center, add2(first_axis, second_axis)),
            add2(center, add2(mul2(first_axis, -1.0), second_axis)),
            add2(center, add2(mul2(first_axis, -1.0), mul2(second_axis, -1.0))),
            add2(center, add2(first_axis, mul2(second_axis, -1.0))),
        )
        if any(
            distance2(points[index], expected) > tolerance
            for index, expected in zip((1, 3, 5, 7), expected_corners)
        ):
            return None
        if first_radius >= second_radius:
            major = add2(center, first_axis)
            minor = add2(center, second_axis)
        else:
            major = add2(center, second_axis)
            minor = add2(center, first_axis)
        return center, major, minor

    def _create_exact_spline_segment(self, sketch, edge, mapper=None):
        controls = list(edge.get('controls') or [])
        knots = [float(value) for value in (edge.get('knots') or [])]
        multiplicities = [int(value) for value in (edge.get('multiplicities') or [])]
        weights = [float(value) for value in (edge.get('weights') or [])]
        if len(controls) < 2 or not knots or len(knots) != len(multiplicities):
            return None

        full_knots = []
        for knot, multiplicity in zip(knots, multiplicities):
            full_knots.extend([float(knot)] * max(0, int(multiplicity)))
        if not full_knots:
            return None
        knot_min = min(full_knots)
        knot_span = max(full_knots) - knot_min
        if knot_span <= 1.0e-15:
            return None
        # ISplineParamData requires knot values in [0, 1]. SimpleCAD stores
        # the canonical B-spline parameterization, which can use any finite
        # affine knot range.
        full_knots = [(value - knot_min) / knot_span for value in full_knots]

        rational = len(weights) == len(controls) and any(
            abs(float(weight) - 1.0) > 1.0e-12 for weight in weights
        )
        closed = bool(edge.get('periodic')) or (
            multiplicities[0] >= int(edge.get('degree', 3)) + 1
            and multiplicities[-1] >= int(edge.get('degree', 3)) + 1
            and _distance(_v3(controls[0]), _v3(controls[-1])) <= 1e-9
        )
        control_values = []
        for index, point in enumerate(controls):
            if mapper is None:
                px, py, pz = _pt_m(point)
            else:
                x, y = mapper(_v3(point))
                px, py, pz = _as_m(x), _as_m(y), 0.0
            if rational:
                weight = float(weights[index])
                if closed:
                    control_values.extend([px, py, pz, weight])
                else:
                    control_values.extend([
                        px * weight, py * weight, pz * weight, weight,
                    ])
            else:
                control_values.extend([px, py, pz])

        param_data = None
        try:
            raw = sketch._oleobj_.InvokeTypes(
                83,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_DISPATCH, 0),
                (),
            )
            if raw is not None:
                param_data = win32com.client.Dispatch(raw)
        except Exception:
            try:
                param_data = sketch.CreateSplineParamData()
            except Exception:
                param_data = None
        if param_data is None:
            return None

        def put_i4(dispid, value):
            try:
                param_data._oleobj_.InvokeTypes(
                    dispid,
                    0,
                    pythoncom.DISPATCH_PROPERTYPUT,
                    (pythoncom.VT_EMPTY, 0),
                    ((pythoncom.VT_I4, pythoncom.PARAMFLAG_FIN),),
                    int(value),
                )
            except Exception:
                names = {1: 'Dimension', 2: 'Order', 3: 'Periodic', 4: 'ControlPointsCount'}
                setattr(param_data, names[dispid], int(value))

        put_i4(1, 4 if rational else 3)
        put_i4(2, int(edge.get('degree', 3)) + 1)
        put_i4(3, 1 if edge.get('periodic') else 0)
        put_i4(4, len(controls))

        control_data = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            control_values,
        )
        knot_data = win32com.client.VARIANT(
            pythoncom.VT_ARRAY | pythoncom.VT_R8,
            full_knots,
        )

        def set_array(dispid, method_name, values):
            try:
                return bool(param_data._oleobj_.InvokeTypes(
                    dispid,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_BOOL, 0),
                    ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                    values,
                ))
            except Exception:
                return bool(getattr(param_data, method_name)(values))

        if not set_array(19, 'SetControlPoints', control_data):
            raise RuntimeError('SolidWorks rejected B-spline control points')
        if not set_array(20, 'SetKnotPoints', knot_data):
            raise RuntimeError('SolidWorks rejected B-spline knots')

        segments = None
        try:
            segments = sketch._oleobj_.InvokeTypes(
                84,
                0,
                pythoncom.DISPATCH_METHOD,
                (pythoncom.VT_VARIANT, 0),
                ((pythoncom.VT_DISPATCH, pythoncom.PARAMFLAG_FIN),),
                param_data,
            )
        except Exception:
            segments = sketch.CreateSplinesByEqnParams2(param_data)
        if not segments:
            return None
        if isinstance(segments, (list, tuple)):
            segment = list(segments)[0]
        else:
            segment = segments
        try:
            return win32com.client.Dispatch(segment)
        except Exception:
            return segment

    def _draw_edge(self, sketch, edge, mapper):
        edge_type = edge.get('type')
        if edge_type == 'line':
            sx, sy = mapper(_v3(edge.get('start')))
            ex, ey = mapper(_v3(edge.get('end')))
            return sketch.CreateLine(_as_m(sx), _as_m(sy), 0.0, _as_m(ex), _as_m(ey), 0.0)
        if edge_type == 'circle':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            x_axis = edge.get('_kernel_x_axis')
            if x_axis is None:
                x_axis, _unused_y_axis = _plane_axes(
                    edge.get('normal') or (0.0, 0.0, 1.0)
                )
            radius_point = _add(center, _mul(_unit(x_axis), radius))
            cx, cy = mapper(center)
            px, py = mapper(radius_point)
            try:
                return sketch.CreateCircle(
                    _as_m(cx), _as_m(cy), 0.0,
                    _as_m(px), _as_m(py), 0.0,
                )
            except Exception:
                return sketch.CreateCircleByRadius(
                    _as_m(cx), _as_m(cy), 0.0, _as_m(radius)
                )
        if edge_type == 'angle_arc':
            center = _v3(edge.get('center'))
            radius = float(edge.get('radius', 1.0))
            start_angle = float(edge.get('start_angle', 0.0))
            end_angle = float(edge.get('end_angle', 0.0))
            span = (end_angle - start_angle) % (2.0 * math.pi)
            if span <= 1.0e-12 and abs(end_angle - start_angle) > 1.0e-12:
                span = 2.0 * math.pi
            middle_angle = start_angle + 0.5 * span
            normal = edge.get('normal') or (0.0, 0.0, 1.0)
            arc_axes = (
                edge.get('_kernel_x_axis'),
                edge.get('_kernel_y_axis'),
            )
            start = _angle_arc_world_point(
                center, radius, start_angle, normal, *arc_axes
            )
            middle = _angle_arc_world_point(
                center, radius, middle_angle, normal, *arc_axes
            )
            end = _angle_arc_world_point(
                center, radius, end_angle, normal, *arc_axes
            )
            sx, sy = mapper(start)
            mx, my = mapper(middle)
            ex, ey = mapper(end)
            return sketch.Create3PointArc(
                _as_m(sx), _as_m(sy), 0.0,
                _as_m(ex), _as_m(ey), 0.0,
                _as_m(mx), _as_m(my), 0.0,
            )
        if edge_type == 'three_point_arc':
            sx, sy = mapper(_v3(edge.get('start')))
            mx, my = mapper(_v3(edge.get('middle')))
            ex, ey = mapper(_v3(edge.get('end')))
            # SolidWorks expects start, end, point-on-arc; SimpleCAD and FreeCAD
            # represent the same arc as start, point-on-arc, end.
            return sketch.Create3PointArc(
                _as_m(sx), _as_m(sy), 0.0,
                _as_m(ex), _as_m(ey), 0.0,
                _as_m(mx), _as_m(my), 0.0,
            )
        if edge_type == 'spline':
            ellipse = self._ellipse_geometry_from_spline(edge, mapper)
            if ellipse is not None:
                center, major, minor = ellipse
                return sketch.CreateEllipse(
                    _as_m(center[0]), _as_m(center[1]), 0.0,
                    _as_m(major[0]), _as_m(major[1]), 0.0,
                    _as_m(minor[0]), _as_m(minor[1]), 0.0,
                )
            coords = []
            for point in edge.get('controls') or []:
                x, y = mapper(_v3(point))
                coords.extend([_as_m(x), _as_m(y), 0.0])
            if len(coords) >= 6:
                try:
                    segment = self._create_exact_spline_segment(sketch, edge, mapper)
                    if segment is not None:
                        return segment
                except Exception as exc:
                    self.logs.append(f'exact B-spline creation failed: {exc}')
                point_data = win32com.client.VARIANT(
                    pythoncom.VT_ARRAY | pythoncom.VT_R8,
                    coords,
                )
                try:
                    previous_add_to_db = bool(sketch.AddToDB)
                except Exception:
                    previous_add_to_db = True
                try:
                    sketch.AddToDB = False
                except Exception:
                    pass
                try:
                    for dispid, arg_types, args in (
                        (
                            69,
                            (
                                (pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),
                                (pythoncom.VT_BOOL, pythoncom.PARAMFLAG_FIN),
                            ),
                            (point_data, True),
                        ),
                        (
                            37,
                            ((pythoncom.VT_VARIANT, pythoncom.PARAMFLAG_FIN),),
                            (point_data,),
                        ),
                    ):
                        try:
                            raw_segment = sketch._oleobj_.InvokeTypes(
                                dispid,
                                0,
                                pythoncom.DISPATCH_METHOD,
                                (pythoncom.VT_DISPATCH, 0),
                                arg_types,
                                *args,
                            )
                            if raw_segment is not None:
                                return win32com.client.Dispatch(raw_segment)
                        except Exception:
                            pass
                    return None
                finally:
                    try:
                        sketch.AddToDB = previous_add_to_db
                    except Exception:
                        pass
        if edge_type == 'helix':
            raise SimpleCADUnsupportedOpError('SolidWorks helix edge construction is not yet supported')
        raise SimpleCADUnsupportedOpError(f'Unsupported profile edge type for SolidWorks sketch: {edge_type}')

    def _draw_3d_edge(self, sketch, edge):
        edge_type = edge.get('type')
        if edge_type == 'line':
            start = _pt_m(edge.get('start'))
            end = _pt_m(edge.get('end'))
            return sketch.CreateLine(*start, *end)
        if edge_type in {'angle_arc', 'three_point_arc'}:
            if edge_type == 'angle_arc':
                center = _v3(edge.get('center'))
                radius = float(edge.get('radius', 1.0))
                start_angle = float(edge.get('start_angle', 0.0))
                end_angle = float(edge.get('end_angle', 0.0))
                span = (end_angle - start_angle) % (2.0 * math.pi)
                if span <= 1.0e-12 and abs(end_angle - start_angle) > 1.0e-12:
                    span = 2.0 * math.pi
                normal = edge.get('normal') or (0.0, 0.0, 1.0)
                arc_axes = (
                    edge.get('_kernel_x_axis'),
                    edge.get('_kernel_y_axis'),
                )
                start = _angle_arc_world_point(
                    center, radius, start_angle, normal, *arc_axes
                )
                middle = _angle_arc_world_point(
                    center,
                    radius,
                    start_angle + 0.5 * span,
                    normal,
                    *arc_axes,
                )
                end = _angle_arc_world_point(
                    center, radius, end_angle, normal, *arc_axes
                )
            else:
                start = _v3(edge.get('start'))
                middle = _v3(edge.get('middle'))
                end = _v3(edge.get('end'))
            return sketch.Create3PointArc(*_pt_m(start), *_pt_m(end), *_pt_m(middle))
        if edge_type == 'spline':
            controls = [_v3(point) for point in (edge.get('controls') or [])]
            if len(controls) < 2:
                raise RuntimeError('A SolidWorks 3D B-spline requires at least two control points')
            try:
                segment = self._create_exact_spline_segment(sketch, edge)
                if segment is not None:
                    return segment
            except Exception as exc:
                self.logs.append(f'exact 3D B-spline creation failed: {exc}')
            point_data = win32com.client.VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8,
                [coordinate for point in controls for coordinate in _pt_m(point)],
            )
            try:
                return sketch.CreateSpline2(point_data, True)
            except Exception:
                return sketch.CreateSpline(point_data)
        if edge_type == 'helix':
            raise SimpleCADUnsupportedOpError('SolidWorks helix path construction is handled separately')
        raise SimpleCADUnsupportedOpError(
            f'Unsupported 3D sweep path edge type for SolidWorks: {edge_type}'
        )

    def _create_3d_path_sketch(self, path, name):
        before_sketches = {
            self._feature_identity(feature)
            for feature in self._features({'3DProfileFeature'})
        }
        self._clear_selection()
        sketch_mgr = self.model.SketchManager
        sketch_mgr.Insert3DSketch(True)
        active_sketch = sketch_mgr.ActiveSketch
        if active_sketch is None:
            raise RuntimeError('SolidWorks did not enter 3D path sketch edit mode')
        created_segments = []
        try:
            sketch_mgr.AddToDB = True
            try:
                sketch_mgr.DisplayWhenAdded = False
            except Exception:
                pass
            for edge in self._profile_edges(path):
                entity = self._draw_3d_edge(sketch_mgr, edge)
                if entity is None:
                    raise RuntimeError(
                        f'SolidWorks rejected a 3D path {edge.get("type", "edge")} entity'
                    )
                created_segments.append(entity)
        finally:
            try:
                sketch_mgr.AddToDB = False
                sketch_mgr.DisplayWhenAdded = True
            except Exception:
                pass
            sketch_mgr.Insert3DSketch(True)

        sketch_feature = None
        try:
            sketch_feature = _maybe_call(active_sketch.GetFeature)
        except Exception:
            pass
        new_sketches = [
            feature
            for feature in self._features({'3DProfileFeature'})
            if self._feature_identity(feature) not in before_sketches
        ]
        if new_sketches:
            sketch_feature = new_sketches[-1]
        if sketch_feature is None:
            raise RuntimeError('SolidWorks did not persist the generated 3D path sketch')
        try:
            sketch_feature.Name = str(name)
        except Exception:
            pass
        self.sketch_segments[self._feature_identity(sketch_feature)] = created_segments
        return sketch_feature

    def _create_profile_sketch(
        self,
        profile,
        axis,
        name,
        *,
        use_profile_offset=False,
        revolve_axis=None,
    ):
        profile_normal = self._profile_normal(profile, axis)
        axis_alignment = max(abs(value) for value in profile_normal)
        if axis_alignment < 1.0 - 1.0e-10:
            _dominant = max(range(3), key=lambda index: abs(float(axis[index])))
            _normal, mapper = self._select_fixed_profile_plane(profile, axis)
            offset = 0.0
        else:
            _dominant, _requested_normal, offset, mapper = self._plane_mapping(
                axis, profile
            )
            if use_profile_offset:
                _dominant, _normal = self._select_profile_plane(axis, offset)
            else:
                _dominant, _normal = self._select_plane(axis)
        before_sketches = {
            self._feature_identity(feature)
            for feature in self._features({'ProfileFeature', '3DProfileFeature'})
        }
        if os.environ.get('SIMPLECAD_SW_TRACE_SKETCHES') == '1':
            _trace_pts = []
            for _edge in self._profile_edges(profile)[:1]:
                _trace_pts.extend(self._edge_points_payload(_edge)[:2])
            self.logs.append(
                f'SKETCH_TRACE create name={name} first_pts={_trace_pts!r} '
                f'axis_aligned={axis_alignment >= 1.0 - 1.0e-10}'
            )
        sketch_mgr = self.model.SketchManager
        sketch_mgr.InsertSketch(True)
        active_sketch = sketch_mgr.ActiveSketch
        if active_sketch is None:
            raise RuntimeError('SolidWorks did not enter profile sketch edit mode')
        try:
            # A reference plane's in-plane axes/origin are owned by SolidWorks.
            # Project through its actual transform, not assumed Top/Right-plane axes.
            if use_profile_offset or axis_alignment < 1.0 - 1.0e-10:
                transform = _maybe_call(active_sketch.ModelToSketchTransform)
                matrix = tuple(float(v) for v in _maybe_call(transform.ArrayData))
                if len(matrix) < 13:
                    raise RuntimeError('SolidWorks returned an incomplete model-to-sketch transform')
                def mapper(point):
                    point_m = _pt_m(point)
                    local = [
                        matrix[12] * sum(point_m[j] * matrix[j * 3 + i] for j in range(3)) + matrix[9 + i]
                        for i in range(3)
                    ]
                    if abs(local[2]) > max(1e-9, max(abs(v) for v in point_m) * 1e-7):
                        raise RuntimeError(f'Profile point lies outside its SolidWorks sketch plane: distance_m={local[2]!r}')
                    return local[0] * M_TO_MM / MODEL_SCALE, local[1] * M_TO_MM / MODEL_SCALE
            try:
                sketch_mgr.AddToDB = True
                try:
                    sketch_mgr.DisplayWhenAdded = False
                except Exception:
                    pass
                created_segments = []
                for edge in self._profile_edges(profile):
                    entity = self._draw_edge(sketch_mgr, edge, mapper)
                    if entity is None:
                        raise RuntimeError(
                            f'SolidWorks rejected a profile {edge.get("type", "edge")} entity'
                        )
                    created_segments.append(entity)
                axis_entity = None
                if revolve_axis is not None:
                    axis_origin, axis_direction = revolve_axis
                    points = []
                    for edge in self._profile_edges(profile):
                        points.extend(self._edge_points_payload(edge))
                    span = max(
                        [
                            _distance(point, axis_origin)
                            for point in points
                            if isinstance(point, (list, tuple))
                        ]
                        or [1.0]
                    )
                    span = max(1.0, span * 1.25)
                    first = _sub(axis_origin, _mul(_unit(axis_direction), span))
                    second = _add(axis_origin, _mul(_unit(axis_direction), span))
                    x1, y1 = mapper(first)
                    x2, y2 = mapper(second)
                    axis_entity = sketch_mgr.CreateCenterLine(
                        _as_m(x1), _as_m(y1), 0.0,
                        _as_m(x2), _as_m(y2), 0.0,
                    )
                    if axis_entity is None:
                        raise RuntimeError('SolidWorks rejected the revolve construction axis')
            finally:
                try:
                    sketch_mgr.AddToDB = False
                    sketch_mgr.DisplayWhenAdded = True
                except Exception:
                    pass
        finally:
            if sketch_mgr.ActiveSketch is not None:
                sketch_mgr.InsertSketch(True)
        sketch_feature = None
        try:
            sketch_feature = _maybe_call(active_sketch.GetFeature)
        except Exception:
            sketch_feature = None
        sketches = self._features({'ProfileFeature', '3DProfileFeature'})
        new_sketches = [
            feature for feature in sketches
            if self._feature_identity(feature) not in before_sketches
        ]
        if new_sketches:
            sketch_feature = new_sketches[-1]
        elif sketches:
            sketch_feature = sketches[-1]
        if sketch_feature is None:
            raise RuntimeError('SolidWorks did not persist the generated profile sketch')
        try:
            sketch_feature.Name = str(name)
        except Exception:
            pass
        self.sketch_segments[self._feature_identity(sketch_feature)] = created_segments
        return sketch_feature, offset, _dominant, _normal, axis_entity

    def _linear_profile_vertices(self, profile):
        try:
            edges = list(self._profile_edges(profile))
        except Exception:
            return []
        if len(edges) < 3 or any(edge.get('type') != 'line' for edge in edges):
            return []
        vertices = [_v3(edge.get('start')) for edge in edges]
        scale = max(
            1.0,
            *(
                _norm(_sub(edge.get('end'), edge.get('start')))
                for edge in edges
            ),
        )
        for index, edge in enumerate(edges):
            if _distance(
                edge.get('end'), vertices[(index + 1) % len(vertices)]
            ) > scale * 1.0e-7:
                return []
        return vertices


__all__ = ["SketchRuntimeMixin"]
