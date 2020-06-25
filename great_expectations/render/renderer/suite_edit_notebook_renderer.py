import os
from typing import Union, Optional, Dict

import nbformat
import jinja2

from great_expectations.core import ExpectationSuite
from great_expectations.core.id_dict import BatchKwargs
from great_expectations.render.renderer.renderer import Renderer
from great_expectations.util import lint_code
from great_expectations.data_context.types.base import NotebookConfig, notebookConfigSchema
from great_expectations.data_context.util import instantiate_class_from_config
from great_expectations.exceptions import SuiteEditNotebookCustomTemplateModuleNotFoundError


class SuiteEditNotebookRenderer(Renderer):
    """
    Render a notebook that can re-create or edit a suite.

    Use cases:
    - Make an easy path to edit a suite that a Profiler created.
    - Make it easy to edit a suite where only JSON exists.
    """
    def __init__(
        self,
        custom_templates_module: Optional[str] = None,
        header_markdown: Optional[NotebookConfig] = None,
    ):
        super().__init__()
        custom_loader = []

        if custom_templates_module:
            try:
                custom_loader = [jinja2.PackageLoader(*custom_templates_module.rsplit('.', 1))]
            except ModuleNotFoundError as e:
                raise SuiteEditNotebookCustomTemplateModuleNotFoundError(custom_templates_module) from e

        loaders = custom_loader + [
            jinja2.PackageLoader('great_expectations.render.notebook_assets', 'suite_edit'),
        ]
        self.template_env = None

        self.template_env = jinja2.Environment(
            loader=jinja2.ChoiceLoader(loaders)
        )

        self.header_markdown = header_markdown


    @staticmethod
    def from_data_context(data_context):
        suite_edit_notebook_config: Optional[NotebookConfig] = None
        if data_context.notebooks and data_context.notebooks.get("suite_edit"):
            suite_edit_notebook_config = notebookConfigSchema.load(data_context.notebooks.get("suite_edit"))

        return instantiate_class_from_config(
            config=suite_edit_notebook_config.__dict__ if suite_edit_notebook_config else {},
            runtime_environment={},
            config_defaults={
                "module_name": "great_expectations.render.renderer.suite_edit_notebook_renderer",
                "class_name": "SuiteEditNotebookRenderer"
            },
        )


    @classmethod
    def _get_expectations_by_column(cls, expectations):
        # TODO probably replace this with Suite logic at some point
        expectations_by_column = {"table_expectations": []}
        for exp in expectations:
            if "column" in exp["kwargs"]:
                col = exp["kwargs"]["column"]

                if col not in expectations_by_column.keys():
                    expectations_by_column[col] = []
                expectations_by_column[col].append(exp)
            else:
                expectations_by_column["table_expectations"].append(exp)

        return expectations_by_column

    @classmethod
    def _build_kwargs_string(cls, expectation):
        kwargs = []
        for k, v in expectation["kwargs"].items():
            if k == "column":
                # make the column a positional argument
                kwargs.append("'{}'".format(v))
            elif isinstance(v, str):
                # Put strings in quotes
                kwargs.append("{}='{}'".format(k, v))
            else:
                # Pass other types as is
                kwargs.append("{}={}".format(k, v))

        return ", ".join(kwargs)

    def add_header(self, suite_name: str, batch_kwargs) -> None:
        if self.header_markdown:
            markdown = self.template_env.get_template(self.header_markdown.file_name).render(suite_name=suite_name, **self.header_markdown.template_kwargs)
        else:
            markdown = self.template_env.get_template("HEADER.md").render(suite_name=suite_name)

        self.add_markdown_cell_str(markdown)

        if not batch_kwargs:
            batch_kwargs = dict()
        self.add_code_cell("header.py", lint=True, suite_name=suite_name, batch_kwargs=batch_kwargs)

    def add_footer(self) -> None:
        self.add_markdown_cell("FOOTER.md")
        # TODO this may become confusing for users depending on what they are trying
        #  to accomplish in their dev loop
        self.add_code_cell("footer.py")

    def add_code_cell(self, code_file: str, lint: bool = False, **template_params) -> None:
        """
        Add the given code as a new code cell.
        """
        template = self.template_env.get_template(code_file)
        code = template.render(**template_params)

        if lint:
            code = lint_code(code).rstrip("\n")

        cell = nbformat.v4.new_code_cell(code)
        self._notebook["cells"].append(cell)

    def add_markdown_cell_str(self, markdown: str) -> None:
        """
        Add the given markdown as a new markdown cell.
        """
        cell = nbformat.v4.new_markdown_cell(markdown)
        self._notebook["cells"].append(cell)

    def add_markdown_cell(self, markdown_file: str, **template_params) -> None:
        """
        Add the given markdown as a new markdown cell.
        """
        template = self.template_env.get_template(markdown_file)

        cell = nbformat.v4.new_markdown_cell(template.render(**template_params))
        self._notebook["cells"].append(cell)

    def add_expectation_cells_from_suite(self, expectations):
        expectations_by_column = self._get_expectations_by_column(expectations)
        self.add_markdown_cell("TABLE_EXPECTATIONS_HEADER.md")
        self._add_table_level_expectations(expectations_by_column)
        # Remove the table expectations since they are dealt with
        expectations_by_column.pop("table_expectations")
        self.add_markdown_cell("COLUMN_EXPECTATIONS_HEADER.md")
        self._add_column_level_expectations(expectations_by_column)

    def _add_column_level_expectations(self, expectations_by_column):
        if not expectations_by_column:
            self.add_markdown_cell("COLUMN_EXPECTATIONS_NOT_FOUND.md")
            return

        for column, expectations in expectations_by_column.items():
            self.add_markdown_cell("COLUMN_EXPECTATIONS.md", column=column)

            for exp in expectations:
                self.add_code_cell(
                    "column_expectation.py",
                    lint=True,
                    expectation=exp,
                    kwargs_string=self._build_kwargs_string(exp),
                    meta_args=self._build_meta_arguments(exp.meta)
                )

    def _add_table_level_expectations(self, expectations_by_column):
        if not expectations_by_column["table_expectations"]:
            self.add_markdown_cell("TABLE_EXPECTATIONS_NOT_FOUND.md")
            return

        for exp in expectations_by_column["table_expectations"]:
            self.add_code_cell(
                "table_expectation.py",
                lint=True,
                expectation=exp,
                kwargs_string=self._build_kwargs_string(exp)
            )

    @staticmethod
    def _build_meta_arguments(meta):
        if not meta:
            return ""

        profiler = "BasicSuiteBuilderProfiler"
        if profiler in meta.keys():
            meta.pop(profiler)

        if meta.keys():
            return ", meta={}".format(meta)

        return ""

    @classmethod
    def write_notebook_to_disk(cls, notebook, notebook_file_path):
        with open(notebook_file_path, "w") as f:
            nbformat.write(notebook, f)

    def render(
        self, suite: ExpectationSuite, batch_kwargs=None
    ) -> nbformat.NotebookNode:
        """
        Render a notebook dict from an expectation suite.
        """
        if not isinstance(suite, ExpectationSuite):
            raise RuntimeWarning("render must be given an ExpectationSuite.")

        self._notebook = nbformat.v4.new_notebook()

        suite_name = suite.expectation_suite_name

        batch_kwargs = self.get_batch_kwargs(suite, batch_kwargs)
        self.add_header(suite_name, batch_kwargs)
        self.add_authoring_intro()
        self.add_expectation_cells_from_suite(suite.expectations)
        self.add_footer()

        return self._notebook

    def render_to_disk(
        self, suite: ExpectationSuite, notebook_file_path: str, batch_kwargs=None
    ) -> None:
        """
        Render a notebook to disk from an expectation suite.

        If batch_kwargs are passed they will override any found in suite
        citations.
        """
        self.render(suite, batch_kwargs)
        self.write_notebook_to_disk(self._notebook, notebook_file_path)

    def add_authoring_intro(self):
        self.add_markdown_cell("AUTHORING_INTRO.md")

    def get_batch_kwargs(
        self, suite: ExpectationSuite, batch_kwargs: Union[dict, BatchKwargs]
    ):
        if isinstance(batch_kwargs, dict):
            return self._fix_path_in_batch_kwargs(batch_kwargs)

        citations = suite.meta.get("citations")
        if not citations:
            return self._fix_path_in_batch_kwargs(batch_kwargs)

        citations = suite.get_citations(require_batch_kwargs=True)
        if not citations:
            return None

        citation = citations[-1]
        batch_kwargs = citation.get("batch_kwargs")
        return self._fix_path_in_batch_kwargs(batch_kwargs)

    @staticmethod
    def _fix_path_in_batch_kwargs(batch_kwargs):
        if isinstance(batch_kwargs, BatchKwargs):
            batch_kwargs = dict(batch_kwargs)
        if batch_kwargs and "path" in batch_kwargs.keys():
            base_dir = batch_kwargs["path"]
            if not os.path.isabs(base_dir):
                batch_kwargs["path"] = os.path.join("..", "..", base_dir)

        return batch_kwargs
