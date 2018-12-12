from pydm.widgets.qtplugin_base import qtplugin_factory, WidgetCategory
from edmbutton import PyDMEDMDisplayButton
# EDM Display Button plugin
print("Loading PyDMEDMDisplayButtonPlugin!")
PyDMEDMDisplayButtonPlugin = qtplugin_factory(PyDMEDMDisplayButton, group=WidgetCategory.DISPLAY, is_container=True)
