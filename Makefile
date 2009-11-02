DESTDIR=/usr
all:

install:
	install -m 755 -d $(DESTDIR)/share/python-support/lintgtk/lintgtk
	install -m 755 -d $(DESTDIR)/share/lintgtk/
	install -m 755 -d $(DESTDIR)/share/lintgtk/lintgtk/
	install -m 755 -d $(DESTDIR)/share/lintgtk/images/
	install -m 755 -d $(DESTDIR)/share/lintgtk/glade/
	install -m 755 -d $(DESTDIR)/bin/
	install -m 755 bin/* $(DESTDIR)/bin
	install -m 755 lintgtk/*.py $(DESTDIR)/share/python-support/lintgtk/lintgtk
	install -m 755 images/* $(DESTDIR)/share/lintgtk/images/
	install -m 755 glade/*.glade $(DESTDIR)/share/lintgtk/glade/
