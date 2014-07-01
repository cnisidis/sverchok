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
from bpy.props import StringProperty, EnumProperty

from node_tree import SverchCustomTreeNode
from data_structure import multi_socket, node_id
from core.update_system import make_tree_from_nodes, do_update


class SvGroupNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupNode'
    bl_label = 'Group'
    bl_icon = 'OUTLINER_OB_EMPTY'

    state = StringProperty(default="NOT_READY", name='state')
    n_id = StringProperty(default='')
    node_dict = {}

    def avail_groups(self, context):
        g = [(n.name, n.name, "") for n in self.id_data.nodes
             if isinstance(n, SvGroupInputsNode)]
        return g

    group_names = EnumProperty(items=avail_groups, name="Groups")

    in_name = StringProperty()
    out_name = StringProperty()

    def draw_buttons(self, context, layout):
        op_name = 'node.sverchok_generic_callback'
        if self.in_name:
            row = layout.row()
            row.label(text="Var:")
            row.label(text=self.in_name)
            op = layout.operator(op_name, text='Unlink')
            op.fn_name = "unlink"
        else:
            layout.prop(self, "group_names")
            op = layout.operator(op_name, text='Link')
            op.fn_name = "link"

    def find_output(self, node):
        if isinstance(node, SvGroupOutputsNode):
            return node
        for socket in node.outputs:
            for link in socket.links:
                new_node = self.find_output(link.to_node)
                if new_node:
                    return new_node
        return None

    def link(self):
        n_id = node_id(self)
        self.state = "NOT_READY"
        group_name = self.group_names
        in_node = self.id_data.nodes.get(group_name)

        if in_node:
            out_node = self.find_output(in_node)
            if not out_node:
                self.state = "INACTIVE"
                return
            self.in_name = in_node.name
            self.out_name = out_node.name
            for socket in in_node.outputs:
                if socket.links:
                    self.inputs.new(socket.bl_idname, socket.name)
            for socket in out_node.inputs:
                if socket.links:
                    self.outputs.new(socket.bl_idname, socket.name)
        update_list = make_tree_from_nodes([in_node.name], self.id_data)
        print(update_list)
        if update_list[-1] == out_node.name:
            self.node_dict[n_id] = update_list
        self.state = "INACTIVE"

    def unlink(self):
        self.state = "INACTIVE"
        self.in_name = ''
        self.out_name = ''
        self.inputs.clear()
        self.outputs.clear()

    def update(self):
        if all((s.links for s in self.inputs)):
            if any((s.links for s in self.outputs)):
                self.state = "ACTIVE"
                return
        self.state = "INACTIVE"

    def process(self):
        n_id = node_id(self)
        in_node = self.id_data.nodes.get(self.in_name)
        out_node = self.id_data.nodes.get(self.out_name)
        #setup data

        for socket in self.inputs:
            if socket.links:
                data = socket.sv_get(deepcopy=False)
                in_node.outputs[socket.name].sv_set(data)
        ul = self.node_dict[n_id]
        do_update(ul[1:-1], self.id_data.nodes)
        for socket in self.outputs:
            if socket.links:
                data = out_node.inputs[socket.name].sv_get(deepcopy=False)
                socket.sv_set(data)


class SvGroupInputsNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupInputsNode'
    bl_label = 'Group Inputs'
    bl_icon = 'OUTLINER_OB_EMPTY'

    state = StringProperty(default="NOT_READY", name='state')
    
    def init(self, context):
        self.outputs.new("StringsSocket","In 0")
        self.state = "INACTIVE"

    def update(self):
        outputs = self.outputs

        if outputs[-1].links:
            length = len(outputs)
            name = "In " + str(length)
            outputs.new("StringsSocket", name)
        else:
            while len(outputs) > 1 and not outputs[-2].links:
                outputs.remove(outputs[-1])

        for i in range(len(outputs)):
            if outputs[i].links:
                other = outputs[i].links[0].to_socket
                if type(outputs[i]) != type(other):
                    others = [l.to_socket for l in outputs[i].links]
                    name = outputs[i].name
                    outputs.remove(outputs[i])
                    outputs.new(other.bl_idname, name)
                    outputs.move(len(outputs)-1, i)
                    for o in others:
                        self.id_data.links.new(outputs[i], o)


class SvGroupOutputsNode(SverchCustomTreeNode):
    bl_idname = 'SvGroupOutputsNode'
    bl_label = 'Group outputs'
    bl_icon = 'OUTLINER_OB_EMPTY'

    state = StringProperty(default="ACTIVE", name='state')
    base_name = StringProperty(default='Data ')
    multi_socket_type = StringProperty(default='StringsSocket')
    
    # just collect sockets
    
    def init(self, context):
        self.inputs.new("StringsSocket","Out 0")
        
    def update(self):
        multi_socket(self, min=1)

    def process(self):
        pass


def register():
    bpy.utils.register_class(SvGroupNode)
    bpy.utils.register_class(SvGroupInputsNode)
    bpy.utils.register_class(SvGroupOutputsNode)

def unregister():
    bpy.utils.unregister_class(SvGroupNode)
    bpy.utils.unregister_class(SvGroupInputsNode)
    bpy.utils.unregister_class(SvGroupOutputsNode)
