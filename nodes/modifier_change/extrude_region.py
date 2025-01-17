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

from mathutils import Matrix, Vector
#from math import copysign

import bpy
from bpy.props import FloatProperty, BoolProperty, EnumProperty
import bmesh.ops

from sverchok.node_tree import SverchCustomTreeNode
from sverchok.data_structure import updateNode, match_long_repeat, repeat_last_for_length
from sverchok.utils.sv_bmesh_utils import bmesh_from_pydata, pydata_from_bmesh
from sverchok.utils.nodes_mixins.sockets_config import ModifierNode

is_290 = bpy.app.version >= (2, 90, 0)

def is_matrix(lst):
    return len(lst) == 4 and len(lst[0]) == 4

def get_faces_center(faces):
    result = Vector((0,0,0))
    for face in faces:
        result += Vector(face.calc_center_median())
    result = (1.0/float(len(faces))) * result
    return result

def get_avg_normal(faces):
    result = Vector((0,0,0))
    for face in faces:
        result += Vector(face.normal)
    result = (1.0/float(len(faces))) * result
    return result

MASK = 0
OUT = 1
IN = 2
MASK_MEANING = {MASK: 'mask', OUT: 'out', IN: 'in'}


class SvExtrudeRegionNode(ModifierNode, SverchCustomTreeNode, bpy.types.Node):
    ''' Extrude region of faces '''
    bl_idname = 'SvExtrudeRegionNode'
    bl_label = 'Extrude Region'
    bl_icon = 'OUTLINER_OB_EMPTY'
    sv_icon = 'SV_EXTRUDE_REGION'

    keep_original: BoolProperty(
        name="Keep original", description="Keep original geometry",
        default=False, update=updateNode)

    transform_modes = [
            ("Matrix", "By matrix", "Transform vertices by specified matrix", 0),
            ("Normal", "Along normal", "Extrude vertices along normal", 1)
        ]

    def update_mode(self, context):
        self.inputs['Matrices'].hide_safe = (self.transform_mode != "Matrix")
        self.inputs['Height'].hide_safe = (self.transform_mode != "Normal")
        self.inputs['Scale'].hide_safe = (self.transform_mode != "Normal")

        if self.transform_mode == "Normal":
            self.multiple = True
        updateNode(self, context)

    transform_mode: EnumProperty(
        name="Transformation mode", description="How vertices transformation is specified",
        default="Matrix", items=transform_modes, update=update_mode)

    height_: FloatProperty(
        name="Height", description="Extrusion amount", default=0.0, update=updateNode)

    scale_: FloatProperty(
        name="Scale", description="Extruded faces scale", default=1.0, min=0.0, update=updateNode)

    multiple: BoolProperty(
        name="Multiple extrude", description="Extrude the same region several times", default=False, update=updateNode)

    mask_type_items = [
            ('mask', "Mask", "Faces that were masked out"),
            ('out',  "Out", "Outer faces of the extrusion"),
            ('in',   "In",  "Inner faces of the extrusion"),
        ]

    mask_out_type : EnumProperty(
            name = "Mask Output",
            items=mask_type_items,
            update=updateNode,
            options={'ENUM_FLAG'},
            default={'out'},
            description="Switch between untouched, inner and outer faces generated by insertion")

    dissolve_ortho_edges : BoolProperty(
            name = "Dissolve Orthogonal Edges",
            description = "Removes and connects edges whose faces form a flat surface and intersect new edges",
            default = False,
            update = updateNode)

    def sv_init(self, context):
        self.inputs.new('SvVerticesSocket', "Vertices")
        self.inputs.new('SvStringsSocket', 'Edges')
        self.inputs.new('SvStringsSocket', 'Polygons')
        self.inputs.new('SvStringsSocket', 'Mask')
        self.inputs.new('SvMatrixSocket', 'Matrices')
        self.inputs.new('SvStringsSocket', "Height").prop_name = "height_"
        self.inputs.new('SvStringsSocket', "Scale").prop_name = "scale_"
        self.inputs.new('SvStringsSocket', "FaceData")

        self.outputs.new('SvVerticesSocket', 'Vertices')
        self.outputs.new('SvStringsSocket', 'Edges')
        self.outputs.new('SvStringsSocket', 'Polygons')
        self.outputs.new('SvVerticesSocket', 'NewVertices')
        self.outputs.new('SvStringsSocket', 'NewEdges')
        self.outputs.new('SvStringsSocket', 'NewFaces')
        self.outputs.new('SvStringsSocket', 'Mask').custom_draw = 'draw_mask_socket'
        self.outputs.new('SvStringsSocket', 'FaceData')

        self.update_mode(context)

    def draw_mask_socket(self, socket, context, layout):
        layout.prop(self, 'mask_out_type', expand=True)
        layout.label(text=socket.name)

    def draw_buttons(self, context, layout):
        layout.prop(self, "transform_mode")
        if self.transform_mode == "Matrix":
            layout.prop(self, "multiple", toggle=True)
        if is_290:
            layout.prop(self, 'dissolve_ortho_edges')

    def draw_buttons_ext(self, context, layout):
        self.draw_buttons(context, layout)
        layout.prop(self, "keep_original", toggle=True)

    def get_out_mask(self, bm, extruded_faces, extruded_verts):
        mask_layer = bm.faces.layers.int.get('mask')
        for face in extruded_faces:
            face[mask_layer] = IN
        # For some reason, bmesh.ops.extrude_face_region gets
        # custom layers data for what we call "outer extrusion geometry"
        # from *surrounding* faces, not from the faces being extruded.
        # So here we have to manually find out the outer geometry.
        for face in bm.faces:
            if face[mask_layer] == MASK:
                if any(v in extruded_verts for v in face.verts):
                    face[mask_layer] = OUT
        mask = [int(MASK_MEANING[face[mask_layer]] in self.mask_out_type) for face in bm.faces]
        return mask

    def process(self):
        # inputs
        if not self.inputs['Vertices'].is_linked:
            return

        vertices_s = self.inputs['Vertices'].sv_get(deepcopy=False)
        edges_s = self.inputs['Edges'].sv_get(default=[[]], deepcopy=False)
        faces_s = self.inputs['Polygons'].sv_get(default=[[]], deepcopy=False)
        masks_s = self.inputs['Mask'].sv_get(default=[[1]], deepcopy=False)
        if self.transform_mode == "Matrix":
            matrices_s = [self.inputs['Matrices'].sv_get(default=[Matrix()], deepcopy=False)]
            heights_s = [0.0]
            scales_s = [1.0]
        else:
            matrices_s = [[]]
            heights_s = self.inputs['Height'].sv_get(deepcopy=False)
            scales_s  = self.inputs['Scale'].sv_get(deepcopy=False)
        if 'FaceData' in self.inputs:
            face_data_s = self.inputs['FaceData'].sv_get(default=[[]], deepcopy=False)
        else:
            face_data_s = [[]]

        need_mask_out = 'Mask' in self.outputs and self.outputs['Mask'].is_linked

        result_vertices = []
        result_edges = []
        result_faces = []
        result_ext_vertices = []
        result_ext_edges = []
        result_ext_faces = []
        result_face_data = []
        result_mask = []

        meshes = match_long_repeat([vertices_s, edges_s, faces_s, masks_s, matrices_s, heights_s, scales_s, face_data_s])

        for vertices, edges, faces, masks, matrix_per_iteration, height_per_iteration, scale_per_iteration, face_data in zip(*meshes):
            if self.transform_mode == "Matrix":
                if not matrix_per_iteration:
                    matrix_per_iteration = [Matrix()]

            if self.multiple:
                if self.transform_mode == "Matrix":
                    n_iterations = len(matrix_per_iteration)
                else:
                    n_iterations = max(len(height_per_iteration), len(scale_per_iteration))
                    height_per_iteration_matched = repeat_last_for_length(height_per_iteration, n_iterations)
                    scale_per_iteration_matched = repeat_last_for_length(scale_per_iteration, n_iterations)
            else:
                n_iterations = 1
                matrix_per_iteration = [matrix_per_iteration]

            mask_matched = repeat_last_for_length(masks,  len(faces))
            if face_data:
                face_data_matched = repeat_last_for_length(face_data, len(faces))

            bm = bmesh_from_pydata(vertices, edges, faces, normal_update=True, markup_face_data=True)
            mask_layer = bm.faces.layers.int.new('mask')
            bm.faces.ensure_lookup_table()
            #fill_faces_layer(bm, masks, 'mask', int, MASK, invert_mask=True)

            b_faces = []
            b_edges = set()
            b_verts = set()
            for mask, face in zip(mask_matched, bm.faces):
                if mask:
                    b_faces.append(face)
                    for edge in face.edges:
                        b_edges.add(edge)
                    for vert in face.verts:
                        b_verts.add(vert)

            extrude_geom = b_faces+list(b_edges)+list(b_verts)

            extruded_verts_last = []
            extruded_bm_verts_all = set()
            extruded_edges_last = []
            extruded_faces_last = []
            extruded_bm_faces_last = []

            matrix_spaces = [Matrix()]

            for idx in range(n_iterations):

                for item in extrude_geom:
                    if isinstance(item, bmesh.types.BMFace):
                        item[mask_layer] = OUT

                if is_290:
                    kwargs = {'use_dissolve_ortho_edges': self.dissolve_ortho_edges}
                else:
                    kwargs = {}

                new_geom = bmesh.ops.extrude_face_region(bm,
                                geom=extrude_geom,
                                edges_exclude=set(),
                                use_keep_orig=self.keep_original,
                                **kwargs)['geom']

                extruded_verts = [v for v in new_geom if isinstance(v, bmesh.types.BMVert)]
                extruded_faces = [f for f in new_geom if isinstance(f, bmesh.types.BMFace)]

                if self.transform_mode == "Matrix":
                    matrices = matrix_per_iteration[idx]
                    if isinstance(matrices, Matrix):
                        matrices = [matrices]
                    matrix_spaces_matched = repeat_last_for_length(matrix_spaces, len(extruded_verts))
                    for vertex_idx, (vertex, matrix) in enumerate(zip(*match_long_repeat([extruded_verts, matrices]))):
                        bmesh.ops.transform(bm, verts=[vertex], matrix=matrix, space=matrix_spaces_matched[vertex_idx])
                        matrix_spaces_matched[vertex_idx] = matrix.inverted() @ matrix_spaces_matched[vertex_idx]
                else:
                    height = height_per_iteration_matched[idx]
                    scale = scale_per_iteration_matched[idx]

                    normal = get_avg_normal(extruded_faces)
                    dr = normal * height
                    center = get_faces_center(extruded_faces)
                    translation = Matrix.Translation(center)
                    rotation = normal.rotation_difference((0,0,1)).to_matrix().to_4x4()
                    m = translation @ rotation
                    bmesh.ops.scale(bm, vec=(scale, scale, scale), space=m.inverted(), verts=extruded_verts)
                    bmesh.ops.translate(bm, verts=extruded_verts, vec=dr)

                extruded_bm_verts_all.update(extruded_verts)
                extruded_verts_last = [tuple(v.co) for v in extruded_verts]

                extruded_edges = [e for e in new_geom if isinstance(e, bmesh.types.BMEdge)]
                extruded_edges_last = [tuple(v.index for v in edge.verts) for edge in extruded_edges]

                extruded_bm_faces_last = extruded_faces
                extruded_faces_last = [[v.index for v in face.verts] for face in extruded_faces]

                extrude_geom = new_geom

            if face_data:
                new_vertices, new_edges, new_faces, new_face_data = pydata_from_bmesh(bm, face_data_matched)
            else:
                new_vertices, new_edges, new_faces = pydata_from_bmesh(bm)
                new_face_data = []

            if need_mask_out:
                new_mask = self.get_out_mask(bm, extruded_bm_faces_last, extruded_bm_verts_all)
                result_mask.append(new_mask)

            bm.free()

            result_vertices.append(new_vertices)
            result_edges.append(new_edges)
            result_faces.append(new_faces)
            result_ext_vertices.append(extruded_verts_last)
            result_ext_edges.append(extruded_edges_last)
            result_ext_faces.append(extruded_faces_last)
            result_face_data.append(new_face_data)

        self.outputs['Vertices'].sv_set(result_vertices)
        self.outputs['Edges'].sv_set(result_edges)
        self.outputs['Polygons'].sv_set(result_faces)
        self.outputs['NewVertices'].sv_set(result_ext_vertices)
        self.outputs['NewEdges'].sv_set(result_ext_edges)
        self.outputs['NewFaces'].sv_set(result_ext_faces)
        if 'Mask' in self.outputs:
            self.outputs['Mask'].sv_set(result_mask)
        if 'FaceData' in self.outputs:
            self.outputs['FaceData'].sv_set(result_face_data)

    def load_from_json(self, node_data: dict, import_version: float):
        if import_version <= 0.08:
            self.mask_out_type = set(node_data.get('mask_out_type', []))


def register():
    bpy.utils.register_class(SvExtrudeRegionNode)


def unregister():
    bpy.utils.unregister_class(SvExtrudeRegionNode)
