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

from node_tree import SverchCustomTreeNode
from data_structure import multi_socket



class SvGroupNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupNode'
    bl_label = 'Group'
    bl_icon = 'OUTLINER_OB_EMPTY'
    
    state = StringProperty(default="NOT_READY", name = 'state')

    
    def draw_buttons(self, context, layout):
        
    def create_sockets(self, context):
        
    def process(self):

class SvGroupInputsNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupNode'
    bl_label = 'Group'
    bl_icon = 'OUTLINER_OB_EMPTY'
    
    state = StringProperty(default="NOT_READY", name = 'state')

    def update(self):

        if outputs[-1].links:
            length = len(outputs)
            name = node.base_name + str(length)
            outputs.new("StringsSocket", name)
        else:
            while len(outputs) > 1 and not outputs[-2].links:
                onputs.remove(onputs[-1]
        for i in range(len(outputs)):
            if outputs[i].links:
                other = outputs[i].links[0].to_socket
                if type(outputs[i]) != type(other):
                    name = outputs[i].name
                    outputs.remove(outputs[i])
                    outputs.new(other.bl_idname,name)
                    
        
class SvGroupOutputsNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupNode'
    bl_label = 'Group'
    bl_icon = 'OUTLINER_OB_EMPTY'
    
    state = StringProperty(default="ACTIVE", name = 'state')
    
    def update(self):
        multi_socket(self, min=1)
    
def register():
    bpy.utils.register_class(SvGroupNode)


def unregister():
    bpy.utils.unregister_class(SvGroupNode)
