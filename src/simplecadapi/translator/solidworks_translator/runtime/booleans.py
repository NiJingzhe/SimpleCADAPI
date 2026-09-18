"""SolidWorks runtime fragment: BooleanRuntimeMixin."""


class BooleanRuntimeMixin:
    def _boolean_result_body(self, value, name):
        if hasattr(value, 'GetFaces'):
            return value
        if isinstance(value, (list, tuple)):
            values = list(value)
        else:
            try:
                values = list(value)
            except Exception:
                values = []
        bodies = [body for body in values if hasattr(body, 'GetFaces')]
        if len(bodies) != 1:
            raise RuntimeError(
                f'SolidWorks body boolean for {name} returned {len(bodies)} solid sections; expected one'
            )
        return bodies[0]

    def _boolean_result_bodies(self, value):
        if hasattr(value, 'GetFaces'):
            return [value]
        if isinstance(value, (list, tuple)):
            values = list(value)
        else:
            try:
                values = list(value)
            except Exception:
                values = []
        return [body for body in values if hasattr(body, 'GetFaces')]

    def _body_intersection_has_volume(self, left, right):
        left_bbox = self._box_from_entity(left)
        right_bbox = self._box_from_entity(right)
        if not _bbox_intersects(left_bbox, right_bbox, tolerance=1.0e-9):
            return False
        try:
            working_left = self._copy_temp_body(left)
            working_right = self._copy_temp_body(right)
            response = working_left.Operations2(
                SWBODYINTERSECT, working_right
            )
            if (
                isinstance(response, tuple)
                and len(response) == 2
                and isinstance(response[1], int)
            ):
                result, error_code = response
            else:
                result, error_code = response, 0
            intersections = self._boolean_result_bodies(result)
            if not intersections:
                return False
            common_volume = sum(
                max(0.0, float(self._body_volume(body) or 0.0))
                for body in intersections
            )
            operand_volumes = [
                max(0.0, float(self._body_volume(body) or 0.0))
                for body in (left, right)
            ]
            tolerance = max(
                1.0e-18,
                min(operand_volumes) * 1.0e-10
                if all(operand_volumes) else 1.0e-18,
            )
            return common_volume > tolerance
        except Exception as exc:
            raise RuntimeError(
                'Could not determine exact SolidWorks body intersection for '
                f'multi-section Cut; left_bbox={left_bbox!r}; '
                f'right_bbox={right_bbox!r}: {exc}'
            ) from exc

    def _body_union_is_single(self, left, right):
        left_bbox = self._box_from_entity(left)
        right_bbox = self._box_from_entity(right)
        if not _bbox_intersects(left_bbox, right_bbox, tolerance=1.0e-9):
            return False
        try:
            working_left = self._copy_temp_body(left)
            working_right = self._copy_temp_body(right)
            response = working_left.Operations2(SWBODYADD, working_right)
            if (
                isinstance(response, tuple)
                and len(response) == 2
                and isinstance(response[1], int)
            ):
                result, error_code = response
            else:
                result, error_code = response, 0
            result_bodies = self._boolean_result_bodies(result)
            if len(result_bodies) == 1:
                return True
            if len(result_bodies) > 1:
                return False
            raise RuntimeError(
                f'Operations2 returned no solid section; error={error_code}'
            )
        except Exception as exc:
            raise RuntimeError(
                'Could not determine exact SolidWorks body connectivity for '
                f'Union; left_bbox={left_bbox!r}; '
                f'right_bbox={right_bbox!r}: {exc}'
            ) from exc

    def _boolean_body(
        self,
        base,
        tools,
        op_code,
        name,
        *,
        skip_non_intersecting=False,
        clean=False,
        allow_split_sections=False,
        prefer_native=False,
    ):
        if not tools:
            return base
        native_fallback_base = None
        native_fallback_tools = None
        if prefer_native:
            try:
                # InsertCombineFeature may consume or invalidate its selected
                # bodies even when feature creation fails.
                # Keep explicit static fallback bodies before that attempt so
                # a failed native probe cannot force source-kernel fallback.
                # Tool bodies must be copied as well as the base: SolidWorks
                # invalidates every selected operand when a native Combine is
                # created, even if it subsequently reports an error.
                native_fallback_base = self._copy_temp_body(base)
                native_fallback_tools = [
                    self._copy_temp_body(tool) for tool in tools
                ]
                # Native Combine consumes every selected operand. Feed it
                # native BCopy=True identity features so the graph remains
                # functional when an operand also has another downstream
                # consumer. Move/Copy Body retains the upstream parametric
                # dependency; a temporary Body2 copy would not.
                degraded_before = len(self.degraded_features)
                live_base = self._transform_body_feature(
                    base, _identity_matrix(), f'{name}_operand_base'
                )
                live_tools = [
                    self._transform_body_feature(
                        tool,
                        _identity_matrix(),
                        f'{name}_operand_tool_{index + 1}',
                    )
                    for index, tool in enumerate(tools)
                ]
                if len(self.degraded_features) != degraded_before:
                    raise RuntimeError(
                        'native Boolean operand copy degraded to a static body'
                    )
                native_result = self._native_combine_body(
                    live_base, live_tools, op_code, name,
                    prefer_live_base=True,
                )
                self.logs.append(f'boolean {name} used live native Combine')
                return native_result
            except Exception as exc:
                self.logs.append(
                    f'live native Combine failed for {name}; using static '
                    f'body fallback: {exc}'
                )
                self._mark_degraded(name, 'static_boolean')
        # Operation-graph nodes are functional: a boolean result must not consume
        # source bodies that can feed other graph branches. Work only on copies.
        result = native_fallback_base or self._copy_temp_body(base)
        pending = list(native_fallback_tools or tools)
        while pending:
            if op_code == SWBODYADD:
                result_bbox = self._box_from_entity(result)
                pending_boxes = [self._box_from_entity(candidate) for candidate in pending]
                candidate_indices = sorted(
                    range(len(pending)),
                    key=lambda index: (
                        not _bbox_intersects(
                            result_bbox,
                            pending_boxes[index],
                            tolerance=1.0e-5,
                        ),
                        _norm(_bbox_axis_gaps(result_bbox, pending_boxes[index])),
                        index,
                    ),
                )
            elif op_code == SWBODYCUT:
                # Set subtraction is independent of tool order. SolidWorks can
                # reject one copied tool with 547 while accepting another tool
                # first; try every pending cutter before escalating to Combine.
                candidate_indices = list(range(len(pending)))
            else:
                candidate_indices = [0]

            attempts = []
            for candidate_index in candidate_indices:
                tool = pending[candidate_index]
                boolean_result = None
                error_code = 0
                for reset_tolerances in (False, True):
                    if reset_tolerances and error_code != 547:
                        break
                    # Operations2 invalidates both input temporary bodies. Always
                    # start an attempt from fresh copies so a failed boolean cannot
                    # corrupt this graph branch or a later retry.
                    working_result = self._copy_temp_body(result)
                    temp_tool = self._copy_temp_body(tool)
                    if reset_tolerances:
                        try:
                            working_result.ResetEdgeTolerances()
                            temp_tool.ResetEdgeTolerances()
                        except Exception as exc:
                            self.logs.append(
                                f'edge tolerance reset failed for {name}: {exc}'
                            )
                    error_code = 0
                    try:
                        response = working_result.Operations2(op_code, temp_tool)
                        if (
                            isinstance(response, tuple)
                            and len(response) == 2
                            and isinstance(response[1], int)
                        ):
                            boolean_result, error_code = response
                        else:
                            boolean_result = response
                    except Exception as exc:
                        self.logs.append(f'Operations2 attempt failed for {name}: {exc}')
                    if not boolean_result:
                        try:
                            # Do not cap this at one section: a disjoint union returns
                            # two bodies, which must be rejected rather than truncated.
                            # Operations2 invalidates its inputs even when it returns an
                            # error code, so the legacy fallback needs fresh copies.
                            legacy_result = self._copy_temp_body(result)
                            legacy_tool = self._copy_temp_body(tool)
                            boolean_result = legacy_result.Operations(
                                op_code, legacy_tool, 1024
                            )
                            if boolean_result:
                                self.logs.append(
                                    f'boolean {name} recovered with legacy body '
                                    f'operation after Operations2 error {error_code}'
                                )
                        except Exception as legacy_exc:
                            self.logs.append(
                                f'legacy body operation attempt failed for {name}: {legacy_exc}'
                            )
                    if boolean_result:
                        break
                if (
                    not boolean_result
                    and op_code == SWBODYCUT
                    and error_code == 547
                ):
                    tool_bbox = self._box_from_entity(tool)
                    for clearance_factor in (
                        1.0 - 1.0e-6,
                        1.0 + 1.0e-6,
                        1.0 - 1.0e-5,
                        1.0 + 1.0e-5,
                        1.0 - 1.0e-4,
                        1.0 + 1.0e-4,
                    ):
                        working_result = self._copy_temp_body(result)
                        temp_tool = self._copy_temp_body(tool)
                        try:
                            self._apply_transform_to_temp_body(
                                temp_tool,
                                _scale_about_bbox_matrix(
                                    tool_bbox, clearance_factor
                                ),
                            )
                            response = working_result.Operations2(
                                op_code, temp_tool
                            )
                            if (
                                isinstance(response, tuple)
                                and len(response) == 2
                                and isinstance(response[1], int)
                            ):
                                boolean_result, error_code = response
                            else:
                                boolean_result = response
                                error_code = 0
                        except Exception as exc:
                            self.logs.append(
                                f'cut clearance attempt failed for {name}; '
                                f'factor={clearance_factor:.9g}: {exc}'
                            )
                            boolean_result = None
                        if boolean_result:
                            self.logs.append(
                                f'cut {name} recovered error 547 with tool '
                                f'clearance factor {clearance_factor:.9g}'
                            )
                            break
                if boolean_result:
                    candidate_bodies = self._boolean_result_bodies(boolean_result)
                    if len(candidate_bodies) > 1:
                        if (
                            op_code == SWBODYCUT
                            and len(pending) > 1
                            and allow_split_sections
                        ):
                            remaining_tools = [
                                candidate
                                for index, candidate in enumerate(pending)
                                if index != candidate_index
                            ]
                            split_results = []
                            for section_index, section in enumerate(candidate_bodies):
                                section_result = self._boolean_body(
                                    section,
                                    remaining_tools,
                                    op_code,
                                    f'{name}_section_{section_index + 1}',
                                    skip_non_intersecting=True,
                                    clean=clean,
                                    allow_split_sections=True,
                                )
                                if isinstance(section_result, list):
                                    split_results.extend(section_result)
                                else:
                                    split_results.append(section_result)
                            return split_results
                    if len(candidate_bodies) > 1:
                        if op_code == SWBODYCUT and len(pending) == 1:
                            self._mark_degraded(name, 'static_boolean_split')
                            self.logs.append(
                                f'cut {name} produced {len(candidate_bodies)} '
                                f'geometrically separate solid sections'
                            )
                            return [
                                self._create_feature_from_body(
                                    body, f'{name}_section_{index + 1}'
                                )
                                for index, body in enumerate(candidate_bodies)
                            ]
                        attempts.append(
                            {
                                'candidate_index': candidate_index,
                                'error': int(error_code),
                                'result': (
                                    f'SolidWorks body boolean for {name} returned '
                                    f'{len(candidate_bodies)} solid sections; expected one'
                                ),
                                'bbox': (
                                    pending_boxes[candidate_index]
                                    if op_code == SWBODYADD
                                    else self._box_from_entity(tool)
                                ),
                            }
                        )
                        continue
                    if len(candidate_bodies) != 1:
                        attempts.append(
                            {
                                'candidate_index': candidate_index,
                                'error': int(error_code),
                                'result': 'SolidWorks body boolean returned no solid section',
                                'bbox': self._box_from_entity(tool),
                            }
                        )
                        continue
                    result = candidate_bodies[0]
                    pending.pop(candidate_index)
                    break
                attempts.append(
                    {
                        'candidate_index': candidate_index,
                        'error': int(error_code),
                        'bbox': (
                            pending_boxes[candidate_index]
                            if op_code == SWBODYADD
                            else self._box_from_entity(tool)
                        ),
                    }
                )
            else:
                error_code = attempts[0]['error'] if attempts else int(error_code)
                if skip_non_intersecting and op_code == SWBODYCUT and error_code in {5, 1067}:
                    pending.pop(0)
                    continue
                if op_code == SWBODYCUT and error_code == 547:
                    # Operations2 is more reliable for ordinary bodies, but
                    # SolidWorks can reject a copied multi-tool cut with 547
                    # even when the native Combine feature accepts the same
                    # geometric bodies. This retry is failure-only and keeps
                    # the graph's geometric body inputs unchanged.
                    try:
                        native_body = self._native_combine_body(
                            result, pending, op_code, name
                        )
                        if native_body is not None:
                            self.logs.append(
                                f'boolean {name} recovered with native Combine '
                                f'after Operations2 error 547'
                            )
                            return native_body
                    except Exception as exc:
                        self.logs.append(
                            f'native Combine retry failed for {name}: {exc}'
                        )
                raise RuntimeError(
                    f'SolidWorks temporary body boolean failed for {name}; '
                    f'error={error_code}; result_bbox={self._box_from_entity(result)!r}; '
                    f'attempts={attempts!r}; recent_logs={self.logs[-12:]!r}'
                )
        if clean:
            cleaned = False
            for call in (
                lambda: result.RemoveRedundantTopology(),
                lambda: result._oleobj_.InvokeTypes(
                    60,
                    0,
                    pythoncom.DISPATCH_METHOD,
                    (pythoncom.VT_BOOL, 0),
                    (),
                ),
            ):
                try:
                    cleaned = bool(call())
                    if cleaned:
                        break
                except Exception as exc:
                    self.logs.append(
                        f'redundant-topology cleanup failed for {name}: {exc}'
                    )
            if not cleaned:
                self.logs.append(
                    f'redundant-topology cleanup was not applied for {name}'
                )
        self._mark_degraded(name, 'static_boolean')
        return self._create_feature_from_body(result, name)

    def _body_matches_native_snapshot(
        self, body, snapshot, volume_relative_tolerance=1.0e-3
    ):
        """Identify a local SW body after rollback or a topology-only edit.

        Both sides come from this document, never from a source-kernel replay.
        """
        expected_bbox = (
            snapshot.get('bbox')
            if isinstance(snapshot, dict)
            else None
        )
        expected_volume = (
            snapshot.get('volume')
            if isinstance(snapshot, dict)
            else None
        )
        if not isinstance(expected_bbox, dict) or expected_volume is None:
            return False
        expected_size = _distance(expected_bbox.get('min'), expected_bbox.get('max'))
        volume = self._body_volume(body)
        volume_error = (
            _relative_error(volume, expected_volume, floor=1.0e-12)
            if volume is not None else float('inf')
        )
        bbox_relative_tolerance = (
            1.0e-4 if volume_error <= 1.0e-8 else 2.0e-6
        )
        bbox_tolerance = max(
            2.0e-7, expected_size * bbox_relative_tolerance
        )
        return (
            _bbox_score(self._box_from_entity(body), expected_bbox) <= bbox_tolerance
            and volume is not None
            and volume_error <= float(volume_relative_tolerance)
        )

    def _combine_op_value(self, op_code):
        if op_code not in {SWBODYADD, SWBODYCUT, SWBODYINTERSECT}:
            raise RuntimeError(f'Unsupported combine operation code: {op_code}')
        return op_code

    def _native_combine_body(
        self, base, tools, op_code, name, *, prefer_live_base=False
    ):
        combine_op = self._combine_op_value(op_code)
        before = self._body_names()
        self._clear_selection()
        if not self._select_entity(base, append=False, mark=1):
            raise RuntimeError('Could not select main body for native Combine')
        for tool in tools:
            if not self._select_entity(tool, append=True, mark=2):
                raise RuntimeError('Could not select tool body for native Combine')
        feature = None
        direct_tools = (
            tuple(tools)
            if op_code == SWBODYCUT
            else tuple([base] + list(tools))
        )
        direct_tool_variants = []
        empty_tool_variants = []
        # InsertCombineFeature's ToolVar is a COM array of Body2 objects.
        # pywin32 can otherwise expose a plain Python tuple as a scalar
        # VARIANT, which SolidWorks rejects with DISP_E_TYPEMISMATCH.  The
        # explicit arrays are required both for the primary live path and for
        # the failure-only retry after temporary-body error 547.
        for variant_type in (
            pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH,
            pythoncom.VT_ARRAY | pythoncom.VT_VARIANT,
        ):
            try:
                direct_tool_variants.append(
                    win32com.client.VARIANT(variant_type, direct_tools)
                )
            except Exception as exc:
                self.logs.append(
                    f'could not marshal Combine tools for {name}: {exc}'
                )
            try:
                empty_tool_variants.append(
                    win32com.client.VARIANT(variant_type, ())
                )
            except Exception as exc:
                self.logs.append(
                    f'could not marshal empty Combine tools for {name}: {exc}'
                )
        empty_main = _empty_dispatch()
        for call in (
            *(
                lambda tool_variant=tool_variant: self.model.FeatureManager.InsertCombineFeature(
                    combine_op,
                    base if op_code == SWBODYCUT else empty_main,
                    tool_variant,
                )
                for tool_variant in direct_tool_variants
            ),
            lambda: self.model.FeatureManager.InsertCombineFeature(
                combine_op, base if op_code == SWBODYCUT else empty_main,
                direct_tools,
            ),
            *(
                lambda empty_tools=empty_tools: self.model.FeatureManager.InsertCombineFeature(
                    combine_op, empty_main, empty_tools
                )
                for empty_tools in empty_tool_variants
            ),
        ):
            try:
                feature = call()
                if feature is not None:
                    break
            except Exception as exc:
                self.logs.append(f'combine attempt failed for {name}: {exc}')
        self._clear_selection()
        if feature is None:
            raise RuntimeError('SolidWorks InsertCombineFeature failed')
        try:
            feature.Name = str(name)
        except Exception:
            pass
        return self._capture_new_body(before, feature)


__all__ = ["BooleanRuntimeMixin"]
