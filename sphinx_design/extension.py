import hashlib
from pathlib import Path

try:
    import importlib.resources as resources
except ImportError:
    # python < 3.7
    import importlib_resources as resources  # type: ignore[no-redef]

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.application import Sphinx
from sphinx.environment import BuildEnvironment
from sphinx.transforms import SphinxTransform
from sphinx.util.docutils import SphinxDirective

from . import compiled as static_module
from .article_info import setup_article_info
from .badges_buttons import setup_badges_and_buttons
from .cards import setup_cards
from .dropdown import setup_dropdown
from .grids import setup_grids
from .icons import setup_icons
from .shared import PassthroughTextElement, create_component
from .tabs import setup_tabs


def setup_extension(app: Sphinx) -> None:
    """Set up the sphinx extension."""
    app.add_config_value("sd_hide_root_title", False, "env")
    app.connect("builder-inited", update_css_js)
    app.connect("env-updated", update_css_links)
    # we override container html visitors, to stop the default behaviour
    # of adding the `container` class to all nodes.container
    app.add_node(
        nodes.container, override=True, html=(visit_container, depart_container)
    )
    app.add_node(
        PassthroughTextElement,
        html=(visit_depart_null, visit_depart_null),
        latex=(visit_depart_null, visit_depart_null),
        text=(visit_depart_null, visit_depart_null),
        man=(visit_depart_null, visit_depart_null),
        texinfo=(visit_depart_null, visit_depart_null),
    )
    app.add_directive(
        "div", Div, override=True
    )  # override sphinx-panels implementation
    app.add_transform(AddFirstTitleCss)
    setup_badges_and_buttons(app)
    setup_cards(app)
    setup_grids(app)
    setup_dropdown(app)
    setup_icons(app)
    setup_tabs(app)
    setup_article_info(app)


def update_css_js(app: Sphinx):
    """Copy the CSS to the build directory."""
    # reset changed identifier
    app.env.sphinx_design_css_changed = False
    # setup up new static path in output dir
    static_path = (Path(app.outdir) / "_sphinx_design_static").absolute()
    static_existed = static_path.exists()
    static_path.mkdir(exist_ok=True)
    app.config.html_static_path.append(str(static_path))
    # Copy JS to the build directory.
    js_path = static_path / "design-tabs.js"
    app.add_js_file(js_path.name)
    if not js_path.exists():
        content = resources.read_text(static_module, "sd_tabs.js")
        js_path.write_text(content)
    # Read the css content and hash it
    content = resources.read_text(static_module, "style.min.css")
    hash = hashlib.md5(content.encode("utf8")).hexdigest()
    # Write the css file
    css_path = static_path / f"design-style.{hash}.min.css"
    app.add_css_file(css_path.name)
    if css_path.exists():
        return
    if static_existed:
        app.env.sphinx_design_css_changed = True
    for path in static_path.glob("*.css"):
        path.unlink()
    css_path.write_text(content, encoding="utf8")


def update_css_links(app: Sphinx, env: BuildEnvironment):
    """If CSS has changed, all files must be re-written, to include the correct stylesheets."""
    if env.sphinx_design_css_changed:
        return list(env.all_docs.keys())


def visit_container(self, node: nodes.Node):
    classes = "docutils container"
    if node.get("is_div", False):
        # we don't want the CSS for container for these nodes
        classes = "docutils"
    self.body.append(self.starttag(node, "div", CLASS=classes))


def depart_container(self, node: nodes.Node):
    self.body.append("</div>\n")


def visit_depart_null(self, node: nodes.Element) -> None:
    """visit/depart passthrough"""


class Div(SphinxDirective):
    """Same as the ``container`` directive, but does not add the ``container`` class in HTML outputs,
    which can interfere with Bootstrap CSS.
    """

    optional_arguments = 1  # css classes
    final_argument_whitespace = True
    option_spec = {"name": directives.unchanged}
    has_content = True

    def run(self):
        self.assert_has_content()
        try:
            if self.arguments:
                classes = directives.class_option(self.arguments[0])
            else:
                classes = []
        except ValueError:
            raise self.error(
                'Invalid class attribute value for "%s" directive: "%s".'
                % (self.name, self.arguments[0])
            )
        node = create_component("div", rawtext="\n".join(self.content), classes=classes)
        self.set_source_info(node)
        self.add_name(node)
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


class AddFirstTitleCss(SphinxTransform):
    """Add a CSS class to to the first sections title."""

    default_priority = 699  # priority main

    def apply(self):
        if not self.app.config.sd_hide_root_title:
            return
        # from sphinx 4 master_doc is deprecated for root_doc
        try:
            if self.env.docname != self.config.root_doc:
                return
        except Exception:
            if self.env.docname != self.config.master_doc:
                return
        for section in self.document.traverse(nodes.section):
            if isinstance(section.children[0], nodes.title):
                if "classes" in section.children[0]:
                    section.children[0]["classes"].append("sd-d-none")
                else:
                    section.children[0]["classes"] = ["sd-d-none"]
            break
