rpm:
	python setup.py bdist --format=rpm

selinux-build:
	make -f /usr/share/selinux/devel/Makefile session_ui.pp
	semodule -i session_ui.pp
selinux-mark:
	chcon -t sessionui_exec_t src/session_ui.py
