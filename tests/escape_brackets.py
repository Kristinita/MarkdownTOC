# coding:utf-8
from base import TestBase
import sublime
import sys

class TestEscapedBrackets(TestBase):
    """Test of attributes 'autolink'"""

    # for debug
    # def tearDown(self):
    #     pass

    square_text = \
"""

<!-- MarkdownTOC autolink="true" {0} -->

<!-- /MarkdownTOC -->


# foo \[bar\]
"""

    def test_square_round(self):
        """handling escaped square brackets"""
        toc_txt = self.commonSetup(self.square_text.format('bracket="round"'))
        self.assert_In('- [foo\[#bar\]](#foo-bar)', toc_txt)
    def test_square_square(self):
        """handling escaped square brackets"""
        toc_txt = self.commonSetup(self.square_text.format('bracket="square"'))
        self.assert_In('- [foo\[#bar\]][foo-bar]', toc_txt)
