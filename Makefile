rpm:
	python setup.py bdist --format=rpm

selinux-build:
	make -f /usr/share/selinux/devel/Makefile sessionui.pp
	semodule -i sessionui.pp
selinux-mark:
	chcon -t sessionui_exec_t src/session_ui.py
