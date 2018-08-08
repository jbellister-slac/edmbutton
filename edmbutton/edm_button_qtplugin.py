from pydm.widgets.qtplugin_base import qtplugin_factory, WidgetCategory
from pydm.widgets.baseplot_qtplugin import qtplugin_plot_factory
from .edm_button import PyDMEDMDisplayButton
# EDM Display Button plugin
print("Loading PyDMEDMDisplayButtonPlugin!")
PyDMEDMDisplayButtonPlugin = qtplugin_factory(PyDMEDMDisplayButton, group=WidgetCategory.DISPLAY, is_container=True)
