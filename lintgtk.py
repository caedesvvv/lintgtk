#!/usr/bin/env python
"""
A pylint checker made with with gtk
"""
import user
import os
import sys

import gtk
import gtksourceview2 as gtksourceview
from kiwi.ui.delegates import GladeDelegate
from kiwi.ui.objectlist import ObjectList, Column
import kiwi.ui.proxywidget # XXX needed for pixbuf

from twisted.internet import gtk2reactor
gtk2reactor.install()
from twisted.internet import threads, reactor

from metamodel import Property
from metamodel import SubscribableModel as Model
from metamodel.datasources.filesource import FileDataSource

from pylint import lint, checkers
from pylint.reporters import BaseReporter

from throbber import Throbber

# funtion to setup some simple style tags
def setup_tags(table):
    """
    Setup the tags table.
    """
    tag_violation = gtk.TextTag('violation')
    tag_violation.set_property('background', '#ccffcc')
    table.add(tag_violation)

###########################################################

class ViolationReport(Model):
    """
    A policy violation report.
    """
    icon = Property(str, '')
    code = Property(str, '')
    message = Property(str, '')
    file = Property(str, '')
    module = Property(str, '')
    object = Property(str, '')
    line = Property(int, 0)


class Stat(object):
    """
    A global status value.
    """
    def __init__(self, name, value):
        self.name = name
        self.value = value

###########################################################
# Main Application Class

class PylintView(GladeDelegate, BaseReporter):
    """
    A dokuwiki editor window
    """
    mapping = {'E':'error',
               'W':'warning',
               'C':'low'}
    def __init__(self):
        self.icons = {}
        GladeDelegate.__init__(self, gladefile="lintgtk",
                          delete_handler=self.quit_if_last)
        self.setup_sourceview()
        self.setup_side()
        self.throbber_icon = Throbber(self.view.throbber)
        self.show_all()

    def setup_config(self):
        """
        Setup configuration file.
        """
        nomondir = os.path.join(user.home,'.pylintgtk')
        if not os.path.exists(nomondir):
            os.mkdir(nomondir)
        cfg = FileDataSource(file=os.path.join(nomondir,'config.caf'))
        cfg.save()
        return cfg

    # quit override to work with twisted
    def quit_if_last(self, *_):
        """
        Quit if we're the last window.
        """
        windows = [toplevel
               for toplevel in gtk.window_list_toplevels()
                   if toplevel.get_property('type') == gtk.WINDOW_TOPLEVEL]
        if len(windows) == 1:
            reactor.stop()

    def setup_sourceview(self):
        """
        Setup the source editor.
        """
        self.buffer = gtksourceview.Buffer()
        tagtable = self.buffer.get_tag_table()
        setup_tags(tagtable)
        lang_manager = gtksourceview.LanguageManager()
        lang = lang_manager.get_language('python')
        self.buffer.set_language(lang)
        self.editor = gtksourceview.View(self.buffer)
        accel_group = gtk.AccelGroup()
        self.get_toplevel().add_accel_group(accel_group)
        self.editor.add_accelerator("paste-clipboard",
                                               accel_group,
                                               ord('v'),
                                               gtk.gdk.CONTROL_MASK,
                                               0)
        self.editor.add_accelerator("copy-clipboard",
                                               accel_group,
                                               ord('c'),
                                               gtk.gdk.CONTROL_MASK,
                                               0)
        self.editor.add_accelerator("cut-clipboard",
                                               accel_group,
                                               ord('x'),
                                               gtk.gdk.CONTROL_MASK,
                                               0)
        self.editor.set_left_margin(5)
        self.editor.set_right_margin(5)
        self.editor.set_show_line_marks(True)
        self.editor.set_show_line_numbers(True)
        self.editor.set_auto_indent(True)
        self.editor.set_insert_spaces_instead_of_tabs(True)
        self.editor.set_highlight_current_line(True)        
        self.editor.set_indent_width(4)
        self.editor.set_indent_on_tab(True)
        high = gtk.gdk.pixbuf_new_from_file("images/red-warning.png")
        medium = gtk.gdk.pixbuf_new_from_file("images/violet-warning.png")
        low = gtk.gdk.pixbuf_new_from_file("images/yellow-warning.png")
        self.icons["low"] = low
        self.icons["warning"] = medium
        self.icons["error"] = high
        self.editor.set_mark_category_pixbuf('error', high)
        self.editor.set_mark_category_pixbuf('warning', medium)
        self.editor.set_mark_category_pixbuf('low', low)                
        self.view.scrolledwindow1.add(self.editor)        

    # setup functions
    def format_icon(self, value):
        """
        return appropriate icon for kiwi.
        """
        priority = self.mapping.get(value[0], 'low')
        return self.icons[priority]

    def setup_side(self):
        """
        Setup the side statistics.
        """
        columns = [Column('code', data_type=gtk.gdk.Pixbuf, format_func=self.format_icon, title=""),
                   Column('line', sorted=True),
                   Column('message'),
                   Column('object'),
                   Column('code')]
        self.problemlist = ObjectList(columns)

        self.view.side_vbox.pack_start(gtk.Label('Violations:'), False, False)
        self.view.side_vbox.add(self.problemlist)
        self.problemlist.connect("selection-changed", self.problem_selected)

        self.view.side_vbox.pack_start(gtk.Label('Stats:'), False, False)
        self.statslist = ObjectList([Column('name'), Column('value')])
        #self.backlinks.connect("selection-changed", self.change_selected)
        self.view.side_vbox.add(self.statslist)

    def problem_selected(self, _, violation):
        """
        A violation was selected on the objectlist.
        """
        if not violation:
            return
        start = self.buffer.get_iter_at_line(violation.line-1)
        end = self.buffer.get_iter_at_line(violation.line-1)
        end.forward_to_line_end()
        self.buffer.place_cursor(start)
        self.editor.scroll_to_iter(start, 0.1)
        self.buffer.select_range(start, end)

    def load_file(self, filename):
        """
        Load and check a file.
        """
        self.linter = lint.PyLinter()
        self.linter.set_reporter(self)
        checkers.initialize(self.linter)
        source_file = open(filename, 'r')
        text = source_file.read()
        source_file.close()
        self.buffer.set_property('text', text)
        self.linecount = self.buffer.get_line_count()
        self.text = text
        self.lastfilename = filename
        self.check()

    def set_score(self, value):
        """
        Set the score widget value.
        """
        scoretext = "<big><big><big>%s</big></big></big>" % (value,)
        self.view.score.set_markup(scoretext)

    def _check_done(self, _):
        """
        A pylint check has finished.
        """
        self.set_score("%.1f"%(self.linter.stats['global_note'],))
        self.view.comments.set_value(self.linter.stats['comment_lines'])
        self.view.lines.set_value(self.linter.stats['code_lines'])
        for key, value in self.linter.stats.iteritems():
            if value.__class__ in [int, str, float]:
                self.statslist.append(Stat(key.replace("_"," "), value))
        self.throbber_icon.stop()
        self.view.progressbar.set_fraction(1.0)

    def _check_error(self, failure):
        """
        There was an error doing the pylint check.
        """
        print self, failure

    def check(self):
        """
        Perform a check on current file.
        """
        self.view.progressbar.set_fraction(0.0)
        self.set_score('?')
        self.throbber_icon.start()
        self.idx = 0
        self.linter = lint.PyLinter()
        self.linter.set_reporter(self)
        checkers.initialize(self.linter)
        deferred = threads.deferToThread(self.linter.check, self.lastfilename)
        deferred.addCallback(self._check_done)
        deferred.addErrback(self._check_error)

    def on_button_save__clicked(self, _):
        """
        Kiwi callback for the save button.
        """
        text = self.buffer.get_property('text')
        sourcefile = open(self.lastfilename, 'w')
        sourcefile.write(text)
        sourcefile.close()
        self.linecount = self.buffer.get_line_count()

        while self.idx > 0:
            mark = self.buffer.get_mark(str(self.idx-1))
            if mark:
                self.buffer.delete_mark(mark)
            self.idx -= 1
        self.idx = 0
        self.problemlist.clear()
        self.statslist.clear()
        start, end = self.buffer.get_bounds()
        self.buffer.remove_source_marks(start, end, 'violation')
        self.buffer.remove_tag_by_name('violation', start, end)
        self.check()

    def _display(self, layout):
        """
        Necessary for pylint.BaseReporter
        """
        pass

    def add_message(self, msg_id, opts, msg):
        """
        A message arrived from the checker thread.
        """
        reactor.callFromThread(self.add_message_main, msg_id, opts, msg)

    def add_message_main(self, msg_id, opts, msg):
        """
        Main thread callback for a message arriving from pylint.
        """
        _, _, obj, line = opts
        self.problemlist.append(ViolationReport(code=msg_id,
                                                icon=msg_id,
                                                line=line, 
                                                object=obj, 
                                                message=msg))
        startiter = self.buffer.get_iter_at_line(line-1)
        enditer = self.buffer.get_iter_at_line(line-1)
        enditer.forward_to_line_end()
        self.buffer.apply_tag_by_name('violation', startiter, enditer)
        fraction = self.linter.stats['statement'] / float(self.linecount)
        self.view.progressbar.set_fraction(fraction)
        priority = self.mapping.get(msg_id[0], 'low')
        self.buffer.create_source_mark(str(self.idx), priority, startiter)
        self.idx += 1

if __name__ == "__main__":
    app = PylintView()
    app.show()
    app.load_file(sys.argv[1])
    reactor.run()

