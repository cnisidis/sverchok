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
from bpy.props import StringProperty, EnumProperty, IntProperty

from node_tree import SverchCustomTreeNode
from data_structure import multi_socket, node_id
from core.update_system import make_tree_from_nodes, do_update
from .group import SvGroupInputsNode, SvGroupOutputsNode


class SvIterNode(SverchCustomTreeNode):
    bl_idname = 'SvIterNode'
    bl_label = 'Iteration'
    bl_icon = 'OUTLINER_OB_EMPTY'

    state = StringProperty(default="NOT_READY", name='state')
    n_id = StringProperty(default='')
    node_dict = {}

    def avail_groups(self, context):
        g = [(n.name, n.name, "") for n in self.id_data.nodes
             if isinstance(n, SvGroupInputsNode)]
        return g

    group_names = EnumProperty(items=avail_groups, name="Groups")
    
    count = IntProperty(default=10, min=1, name="Count")
    
    in_name = StringProperty()
    out_name = StringProperty()

    def draw_buttons(self, context, layout):
        op_name = 'node.sverchok_generic_callback'
        if self.in_name:
            layout.prop(self, "count")
            row = layout.row()
            row.label(text="Group:")
            row.label(text=self.in_name)
            op = layout.operator(op_name, text='Unlink')
            op.fn_name = "unlink"
        else:
            layout.prop(self, "group_names")
            op = layout.operator(op_name, text='Link')
            op.fn_name = "link"

    def find_output(self, node):
        """
        Find matching group output node
        """
        if isinstance(node, SvGroupOutputsNode):
            return node
        for socket in node.outputs:
            for link in socket.links:
                new_node = self.find_output(link.to_node)
                if new_node:
                    return new_node
        return None

    def link(self):
        """
        Link group node by find input node and output node
        and collect thier sockets and create an update list
        for the node group that can be used by process
        Needs lot of sanity checking
        """
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
        n_id = node_id(self)
        if self.in_name and not n_id in self.node_dict:
            update_list = make_tree_from_nodes([self.in_name], self.id_data)
            self.node_dict[n_id] = update_list
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
        # get update list
        ul = self.node_dict[n_id]
        for i in range(self.count):
            do_update(ul[1:-1], self.id_data.nodes)
            for i_s, o_s in zip(in_node.outputs ,out_node.inputs):
                if all((i_s.links, o_s.links)):
                    data = o_s.sv_get(deepcopy=False)
                    i_s.sv_set(data)
                    
        # set output sockets correctly
        for socket in self.outputs:
            if socket.links:
                data = out_node.inputs[socket.name].sv_get(deepcopy=False)
                socket.sv_set(data)


def register():
    bpy.utils.register_class(SvIterNode)

def unregister():
    bpy.utils.unregister_class(SvIterNode)
