from advocu_manager.templates import (
    DESCRIPTION_MAX_LENGTH,
    _build_resources_html,
    _format_title,
    _inline,
    _md_to_html,
)


class TestInline:
    def test_bold(self):
        assert _inline("This is **bold** text") == "This is <strong>bold</strong> text"

    def test_italic(self):
        assert _inline("This is _italic_ text") == "This is <em>italic</em> text"

    def test_link(self):
        assert _inline("[label](https://example.com)") == (
            '<a href="https://example.com" rel="nofollow">label</a>'
        )

    def test_escapes_bare_ampersand(self):
        assert _inline("Tools & Memory") == "Tools &amp; Memory"

    def test_does_not_double_escape_existing_entity(self):
        assert _inline("Tools &amp; Memory") == "Tools &amp; Memory"

    def test_link_url_with_single_underscore_is_untouched(self):
        # Regression: a lone "_" must not be treated as an italic delimiter.
        html = _inline("[Notebook](https://example.com/exit_loop)")
        assert html == '<a href="https://example.com/exit_loop" rel="nofollow">Notebook</a>'

    def test_link_url_with_multiple_underscores_survives_italic_pass(self):
        # Regression for the bug found submitting the Build with AI Curitiba
        # workshop draft: a Colab/GitHub URL with several "_" (e.g. a
        # filename like ADK_Agent_Foundry_1.ipynb) used to get mangled into
        # "<em>" tags because the italic regex ran *after* the link was
        # already inlined as an <a href="..."> string.
        url = (
            "https://colab.research.google.com/github/ahirtonlopes/"
            "build-with-ai-curitiba-2026/blob/main/ADK_Agent_Foundry_1.ipynb"
        )
        html = _inline(f"[Notebook 1]({url})")
        assert html == f'<a href="{url}" rel="nofollow">Notebook 1</a>'
        assert "<em>" not in html
        assert "</em>" not in html
        # Every underscore from the original URL must still be present.
        assert html.count("_") == url.count("_")

    def test_link_label_with_underscore_and_separate_italic_in_same_line(self):
        # Two independent underscore-driven constructs on one line: a link
        # whose label contains "_" (not markdown, just a literal character)
        # and unrelated italic emphasis later in the sentence.
        html = _inline(
            'Check [this_link](https://example.com/a_b_c) and _emphasis_ too.'
        )
        assert html == (
            'Check <a href="https://example.com/a_b_c" rel="nofollow">this_link</a>'
            " and <em>emphasis</em> too."
        )

    def test_bold_and_link_together(self):
        html = _inline("**Bold** and [a link](https://example.com/path_here)")
        assert html == (
            '<strong>Bold</strong> and <a href="https://example.com/path_here" '
            'rel="nofollow">a link</a>'
        )


class TestMdToHtml:
    def test_single_paragraph(self):
        assert _md_to_html("Hello world") == "<p>Hello world</p>"

    def test_blank_line_becomes_empty_paragraph(self):
        html = _md_to_html("First.\n\nSecond.")
        assert html == "<p>First.</p>\n<p></p>\n<p>Second.</p>"

    def test_bullet_list_markers(self):
        for marker in ("* ", "- ", "→ ", "• "):
            html = _md_to_html(f"{marker}item one\n{marker}item two")
            assert html == "<ul>\n <li>item one</li>\n <li>item two</li>\n</ul>", marker

    def test_list_closes_before_following_paragraph(self):
        html = _md_to_html("* item\n\nAfter list.")
        assert html == "<ul>\n <li>item</li>\n</ul>\n<p></p>\n<p>After list.</p>"

    def test_list_with_links_containing_underscores(self):
        html = _md_to_html(
            "* [Notebook 1](https://colab.research.google.com/a_b_1.ipynb)\n"
            "* [Notebook 2](https://colab.research.google.com/c_d_2.ipynb)"
        )
        assert "a_b_1.ipynb" in html
        assert "c_d_2.ipynb" in html
        assert "<em>" not in html


class TestBuildResourcesHtml:
    def test_empty(self):
        assert _build_resources_html([]) == ""

    def test_single_resource(self):
        html = _build_resources_html([("Slides", "https://example.com/slides")])
        assert '<a href="https://example.com/slides" rel="nofollow">Slides</a>' in html
        assert "<strong>Resources:</strong>" in html

    def test_multiple_resources_preserve_order(self):
        html = _build_resources_html([("A", "https://a.example"), ("B", "https://b.example")])
        assert html.index("A") < html.index("B")


class TestFormatTitle:
    def test_basic(self):
        title = _format_title("Speaker", "DevFest Berlin", "Intro to ADK", "EN-US")
        assert title == "Speaker @ DevFest Berlin - Intro to ADK (EN-US)"


def test_description_max_length_constant():
    # Advocu returns HTTP 400 ("expected maxLength: 2000") past this size.
    assert DESCRIPTION_MAX_LENGTH == 2000
