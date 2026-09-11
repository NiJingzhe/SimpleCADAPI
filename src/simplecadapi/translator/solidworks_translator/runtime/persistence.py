"""SolidWorks runtime fragment: PersistenceRuntimeMixin."""


class PersistenceRuntimeMixin:
    def _open_document(self, path, document_type, options=SW_OPEN_DOC_OPTIONS_SILENT):
        # The two LONG [in,out] arguments accept integer inputs under makepy,
        # then return alongside the document. Explicit VARIANT objects only
        # work with late binding and fail with the version-bound ISldWorks.
        result = self.sw._oleobj_.InvokeTypes(
            167, 0, 1, (9, 0),
            ((8, 1), (3, 1), (3, 1), (8, 1), (16387, 3), (16387, 3)),
            os.path.abspath(path), int(document_type), int(options), '', 0, 0,
        )
        if not isinstance(result, tuple) or len(result) != 3:
            raise RuntimeError(f'Unexpected SolidWorks OpenDoc6 result: {result!r}')
        document, errors, warnings = result
        if document is not None:
            document = win32com.client.Dispatch(document)
        return document, int(errors), int(warnings)

    def _activate_document(self, title):
        result = self.sw._oleobj_.InvokeTypes(
            306, 0, 1, (9, 0),
            ((8, 1), (11, 1), (3, 1), (16387, 3)),
            str(title), False, 1, 0,
        )
        if not isinstance(result, tuple) or len(result) != 2:
            raise RuntimeError(f'Unexpected SolidWorks ActivateDoc3 result: {result!r}')
        document, errors = result
        errors = int(errors)
        # swDocNeedsRebuildWarning=2 is not swGenericActivateError=1.
        if document is None or errors not in (0, 2):
            raise RuntimeError(
                f'Could not activate SolidWorks document {title!r}; errors={errors}'
            )
        document = win32com.client.Dispatch(document)
        if errors == 2:
            document.ForceRebuild3(False)
        return document

    def _save_step(self, output_path):
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        if os.path.exists(output_path):
            os.remove(output_path)
        errors = _byref_i4()
        warnings = _byref_i4()
        ok = self.model.Extension.SaveAs(
            output_path,
            SW_SAVE_AS_CURRENT_VERSION,
            SW_SAVE_AS_OPTIONS_SILENT,
            _empty_dispatch(),
            errors,
            warnings,
        )
        if not ok or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(
                f'SolidWorks SaveAs STEP failed: ok={ok!r}, errors={errors.value}, warnings={warnings.value}'
            )

    def _save_native_part(self, output_path):
        output_path = os.path.abspath(output_path)
        os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)
        errors = _byref_i4()
        warnings = _byref_i4()
        try:
            current_path = os.path.abspath(
                str(_maybe_call(self.model.GetPathName) or '')
            )
        except Exception:
            current_path = ''
        if current_path and os.path.normcase(current_path) == os.path.normcase(
            output_path
        ):
            ok = self.model.Save3(
                SW_SAVE_AS_OPTIONS_SILENT, errors, warnings
            )
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            ok = self.model.Extension.SaveAs(
                output_path,
                SW_SAVE_AS_CURRENT_VERSION,
                SW_SAVE_AS_OPTIONS_SILENT,
                _empty_dispatch(),
                errors,
                warnings,
            )
        if not ok or not os.path.exists(output_path) or os.path.getsize(output_path) <= 0:
            raise RuntimeError(
                f'SolidWorks SaveAs SLDPRT failed: ok={ok!r}, errors={errors.value}, warnings={warnings.value}'
            )
        print(
            'SIMPLECAD_SW_NATIVE_PART=' + os.path.abspath(output_path),
            flush=True,
        )

    def _reopen_native_part(self, output_path):
        output_path = os.path.abspath(output_path)
        self._stop_solidworks()
        self._start_solidworks()
        reopened, errors, warnings = self._open_document(output_path, SW_DOC_PART)
        if reopened is None or errors != 0:
            raise RuntimeError(
                f'SolidWorks could not reopen native baseline; '
                f'errors={errors} warnings={warnings}'
            )
        self._require_document_type(reopened, SW_DOC_PART, 'reopened part')
        reopened_path = os.path.abspath(str(_maybe_call(reopened.GetPathName) or ''))
        if os.path.normcase(reopened_path) != os.path.normcase(output_path):
            raise RuntimeError(
                f'SolidWorks reopened the wrong native document: '
                f'expected={output_path!r}, actual={reopened_path!r}'
            )
        self.model = reopened
        self.logs.append(
            f'reopened native baseline for topology persistence: '
            f'{output_path}'
        )

    def _new_part(self):
        return self._new_document('part')

    def _new_document(self, kind):
        if kind == 'part':
            template = self._part_template()
            document_type = SW_DOC_PART
        elif kind == 'assembly':
            template = self._assembly_template()
            document_type = 2
        else:
            raise ValueError(f'Unsupported SolidWorks document kind: {kind!r}')
        if not template:
            raise RuntimeError(
                f'No {kind} template was found for SolidWorks '
                f'{self.solidworks_version}; configure its default document template'
            )
        try:
            model = self.sw.NewDocument(template, 0, 0.0, 0.0)
        except Exception as exc:
            raise RuntimeError(
                f'SolidWorks {self.solidworks_version} could not create '
                f'a {kind} document from template {template!r}'
            ) from exc
        if model is None:
            raise RuntimeError(
                f'SolidWorks {self.solidworks_version} did not create '
                f'a {kind} document from template {template!r}'
            )
        self._require_document_type(model, document_type, f'new {kind}')
        return model

    def _require_document_type(self, model, expected, operation):
        try:
            actual = int(_maybe_call(model.GetType))
        except Exception as exc:
            raise RuntimeError(
                f'Could not verify SolidWorks document type for {operation}'
            ) from exc
        if actual != expected:
            raise RuntimeError(
                f'SolidWorks returned the wrong document type for {operation}: '
                f'expected={expected}, actual={actual}'
            )

    def _part_template(self):
        return self._document_template(8, 'prtdot')

    def _template_matches_version(self, template):
        import re

        years = re.findall(r'(?i)solidworks[ _-]*(20\d{2})(?!\d)', str(template))
        return all(year == self.solidworks_version for year in years)

    def _document_template(self, preference, extension):
        try:
            template = str(self.sw.GetUserPreferenceStringValue(preference) or '')
            if (
                template
                and template.lower().endswith('.' + extension)
                and self._template_matches_version(template)
                and os.path.isfile(template)
            ):
                return template
        except Exception:
            pass
        program_data = os.environ.get('PROGRAMDATA') or r'C:\ProgramData'
        candidates = glob.glob(os.path.join(
            program_data, 'SOLIDWORKS',
            'SOLIDWORKS ' + self.solidworks_version, 'templates', '*.' + extension,
        ))
        for candidate in sorted(candidates, key=str.casefold):
            if self._template_matches_version(candidate) and os.path.isfile(candidate):
                return candidate
        return ''

    def _set_document_title(self, document_name):
        try:
            self.model.SetTitle2(str(document_name))
        except Exception:
            pass

    def _set_mmgs_units(self):
        try:
            self.model.SetUnits(0, 0, 0, 3, False)
        except Exception:
            pass

    def _prune_to_bodies(self, final_bodies, retained_bodies=()):
        resolved = []
        seen_keys = set()
        for body in final_bodies:
            fresh = self._resolve_body_reference(body) or body
            key = self._body_geometry_key(fresh)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            resolved.append(fresh)

        retained = []
        for body in retained_bodies or ():
            fresh = self._resolve_body_reference(body) or body
            key = self._body_geometry_key(fresh)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            retained.append(fresh)

        all_bodies = self._solid_bodies()
        result_keys = {self._body_geometry_key(body) for body in resolved}
        keep_keys = {
            self._body_geometry_key(body) for body in resolved + retained
        }
        discard = [
            body for body in all_bodies
            if self._body_geometry_key(body) not in keep_keys
        ]
        if discard and resolved:
            self._clear_selection()
            selected = 0
            for body in resolved + retained:
                if self._select_entity(body, append=selected > 0):
                    selected += 1
            if selected == len(resolved) + len(retained):
                feature = None
                try:
                    feature = self.model.FeatureManager.InsertDeleteBody2(True)
                except Exception as exc:
                    self.logs.append(f'keep-body feature failed: {exc}')
                self._clear_selection()
                if feature is not None:
                    try:
                        feature.Name = 'SimpleCAD_KeepResultBodies'
                    except Exception:
                        pass
                    try:
                        self.model.ForceRebuild3(False)
                    except Exception:
                        pass
                    remaining = self._solid_bodies()
                    remaining_keys = {
                        self._body_geometry_key(body) for body in remaining
                    }
                    extras = remaining_keys - keep_keys
                    if remaining and not extras:
                        remaining_results = [
                            body for body in remaining
                            if self._body_geometry_key(body) in result_keys
                        ]
                        if len(remaining_results) == len(result_keys):
                            return remaining_results
                        self.logs.append(
                            'keep-body feature could not resolve all result '
                            'bodies after retaining assembly sources'
                        )
                    self.logs.append(
                        f'keep-body feature left {len(extras)} intermediate bodies'
                    )
            else:
                self.logs.append(
                    f'could not select all final bodies for pruning: '
                    f'{selected}/{len(resolved) + len(retained)}'
                )
                self._clear_selection()

        for body in all_bodies:
            hide = self._body_geometry_key(body) not in keep_keys
            try:
                body.HideBody(bool(hide))
            except Exception as exc:
                if hide:
                    try:
                        body.Hide(self.model)
                    except Exception:
                        self.logs.append(f'could not hide intermediate body: {exc}')
        self._clear_selection()
        return resolved

    def _restore_model_scale(self, final_bodies, retained_bodies=()):
        if MODEL_SCALE <= 1.0 + 1.0e-12:
            return final_bodies
        self._clear_selection()
        selected = 0
        for body in final_bodies:
            if self._select_entity(body, append=selected > 0):
                selected += 1
        factor = 1.0 / MODEL_SCALE
        feature = None
        if selected == len(final_bodies):
            try:
                feature = self.model.FeatureManager.InsertScale(
                    1, True, factor, factor, factor
                )
            except Exception as exc:
                self.logs.append(f'combined final scale failed: {exc}')
        else:
            self.logs.append(
                f'combined final scale could not select all result bodies: '
                f'{selected}/{len(final_bodies)}; using per-body transform'
            )
        self._clear_selection()
        if feature is None:
            self._mark_degraded(
                'SimpleCAD_RestoreModelScale', 'static_scale'
            )
            scale_matrix = _identity_matrix()
            scale_matrix[12] = factor
            scaled_bodies = []
            for index, body in enumerate(final_bodies):
                temp_body = self._copy_temp_body(body)
                self._apply_transform_to_temp_body(temp_body, scale_matrix)
                scaled_bodies.append(
                    self._create_feature_from_body(
                        temp_body,
                        f'SimpleCAD_RestoreModelScale_{index + 1}',
                    )
                )
            if not scaled_bodies:
                raise RuntimeError(
                    'SolidWorks failed to restore the canonical model scale'
                )
            return self._prune_to_bodies(
                scaled_bodies, retained_bodies=retained_bodies
            )
        try:
            feature.Name = 'SimpleCAD_RestoreModelScale'
        except Exception:
            pass
        try:
            self.model.ForceRebuild3(False)
        except Exception:
            pass
        bodies = self._solid_bodies()
        result_names = {
            self._body_name(body) for body in final_bodies
        }
        resolved = [
            body for body in bodies
            if self._body_name(body) in result_names
        ]
        return resolved if len(resolved) == len(result_names) else final_bodies


__all__ = ["PersistenceRuntimeMixin"]
