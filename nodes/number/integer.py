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
from bpy.props import IntProperty, StringProperty
from node_tree import SverchCustomTreeNode
from data_structure import updateNode, SvSetSocketAnyType, SvGetSocketAnyType


class IntegerNode(SverchCustomTreeNode):
    ''' Integer '''
    bl_idname = 'IntegerNode'
    bl_label = 'Integer'
    bl_icon = 'OUTLINER_OB_EMPTY'

    int_ = IntProperty(name='Int', description='integer number',
                       default=1,
                       options={'ANIMATABLE'}, update=updateNode)

    state = StringProperty(default="NOT_READY", name = 'state')

    def init(self, context):
        self.inputs.new('StringsSocket', "Integer", "Integer").prop_name = 'int_'
        self.outputs.new('StringsSocket', "Integer", "Integer")

    def update(self):
        print("update called {0}".format(self.name))
        if len(self.outputs):
            self.state = "ACTIVE"
        
    def process(self):
        number = self.inputs[0].sv_get()[0][0]
        self.outputs[0].sv_set([[number]])
        

def register():
    bpy.utils.register_class(IntegerNode)


def unregister():
    bpy.utils.unregister_class(IntegerNode)
