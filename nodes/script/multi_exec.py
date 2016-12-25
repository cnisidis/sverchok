# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

import bpy
from bpy.props import StringProperty

import sverchok
from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode


lines = """\
for i, i2 in zip(V1, V2):
    append([x + y for x, y in zip(i, i2)])
""".strip().split('\n')


def update_wrapper(self, context):
    try:
        updateNode(context.node, context)
    except:
        ...


# Assign a collection
class SvExecNodeDynaStringItem(bpy.types.PropertyGroup):
    line = bpy.props.StringProperty(name="line to eval", default="", update=update_wrapper)


class SvExecNodeModCallback(bpy.types.Operator):

    bl_idname = "node.callback_execnodemod"
    bl_label = "generic callback"

    cmd = bpy.props.StringProperty(default='')

    def execute(self, context):
        getattr(context.node, self.cmd)(self)
        return {'FINISHED'}


class SvExecNodeMod(bpy.types.Node, SverchCustomTreeNode):
    ''' Objects Input Lite'''
    bl_idname = 'SvExecNodeMod'
    bl_label = 'Exec Node Mod'
    bl_icon = 'OUTLINER_OB_EMPTY'

    dynamic_strings = bpy.props.CollectionProperty(type=SvExecNodeDynaStringItem)

    def draw_buttons(self, context, layout):
        if len(self.dynamic_strings) == 0:
            return

        if not context.active_node == self:
            b = layout.box()
            col = b.column(align=True)
            for idx, line in enumerate(self.dynamic_strings):
                col.prop(self.dynamic_strings[idx], "line", text="", emboss=False)
        else:
            col = layout.column(align=True)
            for idx, line in enumerate(self.dynamic_strings):
                col.prop(self.dynamic_strings[idx], "line", text="")

        row = layout.row(align=True)
        # add() remove() clear() move()
        row.operator('node.callback_execnodemod', text='', icon='ZOOMIN').cmd = 'add_new_line'
        row.operator('node.callback_execnodemod', text='', icon='ZOOMOUT').cmd = 'remove_last_line'

    def add_new_line(self, context):
        self.dynamic_strings.add().line = ""

    def remove_last_line(self, context):
        if len(self.dynamic_strings) > 1:
            self.dynamic_strings.remove(len(self.dynamic_strings)-1)


    def sv_init(self, context):
        self.inputs.new('StringsSocket', 'V1')
        self.inputs.new('StringsSocket', 'V2')
        self.inputs.new('StringsSocket', 'V3')
        self.outputs.new('StringsSocket', 'out')

        # add default strings
        self.dynamic_strings.add().line = lines[0]
        self.dynamic_strings.add().line = lines[1]
        self.dynamic_strings.add().line = ""


    def process(self):
        v1,v2,v3 = self.inputs
        V1, V2, V3 = v1.sv_get(0), v2.sv_get(0), v3.sv_get(0)
        out = []
        extend = out.extend
        append = out.append
        exec('\n'.join([j.line for j in self.dynamic_strings]))
        
        self.outputs[0].sv_set(out)
        

def register():
    bpy.utils.register_class(SvExecNodeDynaStringItem)
    bpy.utils.register_class(SvExecNodeMod)
    bpy.utils.register_class(SvExecNodeModCallback)


def unregister():
    bpy.utils.unregister_class(SvExecNodeModCallback)
    bpy.utils.unregister_class(SvExecNodeMod)
    bpy.utils.unregister_class(SvExecNodeDynaStringItem)
