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

# made by: Linus Yng

import io
import csv
import collections
import ast
import locale
import json
import itertools
import pprint

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from node_tree import SverchCustomTreeNode, StringsSocket
from data_structure import (node_id, multi_socket, get_socket_type,
                            updateNode, SvGetSocketAnyType, SvSetSocketAnyType)


# TODO,
# load and dump to/from external file
# update stability, do not disconnect unless something changed
# fix colors for TextOut
#


# status colors
FAIL_COLOR = (0.05, 0.05, 0.1)
READY_COLOR = (0.5, 0.5, 1)


# utility function
def new_output_socket(node, name, type):
    if type == 'v':
        node.outputs.new('VerticesSocket', name, name)
    if type == 's':
        node.outputs.new('StringsSocket', name, name)
    if type == 'm':
        node.outputs.new('MatrixSocket', name, name)


# call structure
# op load->load->load-mode->get_data
# op reset-> reset. remove outputs, any data. as new
# op reload -> reload file without changing socket
# update if current_text and text cache:
#           get data and dispatch to sockets
# update if current_text and not text cache
#               try to reload()
# Test for one case and the others


class SvTextInNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Text Input '''
    bl_idname = 'SvTextInNode'
    bl_label = 'Text Input'
    bl_icon = 'OUTLINER_OB_EMPTY'

    csv_data = {}
    list_data = {}
    json_data = {}

    # general settings
    n_id = StringProperty(default='')

    def avail_texts(self, context):
        texts = bpy.data.texts
        items = [(t.name, t.name, "") for t in texts]
        return items

    text = EnumProperty(items=avail_texts, name="Texts",
                        description="Choose text to load", update=updateNode)

    text_modes = [("CSV", "Csv", "Csv data", "", 1),
                  ("SV", "Sverchok", "Python data", "", 2),
                  ("JSON", "JSON", "Sverchok JSON", 3)]

    textmode = EnumProperty(items=text_modes, default='CSV', update=updateNode, )

    # name of loaded text, to support reloading
    current_text = StringProperty(default="")
    # external file
    file = StringProperty(subtype='FILE_PATH')

# csv standard dialect as defined in http://docs.python.org/3.3/library/csv.html
# below are csv settings, user defined are set to 10 to allow more settings be added before
# user defined.
# to add ; as delimiter and , as decimal mark

    csv_dialects = [('excel',      'Excel',        'Standard excel',   1),
                    ('excel-tab',  'Excel tabs',   'Excel tab format', 2),
                    ('unix',       'Unix',         'Unix standard',    3),
                    ('semicolon',  'Excel ;,',     'Excel ; ,',        4),
                    ('user',       'User defined', 'Define settings', 10), ]

    csv_dialect = EnumProperty(items=csv_dialects, name="Csv Dialect",
                               description="Choose csv dialect", default='excel',
                               update=updateNode)

    csv_delimiters = [(',',  ",",    "Comma: ,",    1),
                      ('\t', 'tab',  "Tab",          2),
                      (';',  ';',    "Semi-colon ;", 3),
                      ('CUSTOM', 'custom', "Custom",  10), ]

    csv_delimiter = EnumProperty(items=csv_delimiters, default=',')
    csv_custom_delimiter = StringProperty(default=':')

    csv_decimalmarks = [('.',       ".",        "Dot",          1),
                        (',',       ',',        "Comma",        2),
                        ('LOCALE',  'Locale',   "Follow locale", 3),
                        ('CUSTOM', 'custom',    "Custom",       10), ]

    csv_decimalmark = EnumProperty(items=csv_decimalmarks, default='LOCALE')
    csv_custom_decimalmark = StringProperty(default=',')
    csv_header = BoolProperty(default=False)

# Sverchok list options
# choose which socket to interpretate data as
    socket_types = [('v', 'Vertices',  "Point, vector or vertices data", 1),
                    ('s', 'Data',    "Generals numbers or edge polygon data", 2),
                    ('m', 'Matrix',  "Matrix data", 3), ]
    socket_type = EnumProperty(items=socket_types, default='s')

    #interesting but dangerous, TODO
    reload_on_update = BoolProperty(default=False, description="Reload text file on every update")

    def draw_buttons(self, context, layout):

        if self.current_text:
            layout.label(text="File: {0} loaded".format(self.current_text))
            #layout.prop(self,'reload_on_update','Reload every update')
            layout.operator('node.sverchok_generic_callback', text='Reload').fn_name = 'reload'
            layout.operator('node.sverchok_generic_callback', text='Reset').fn_name = 'reset'
        else:
            layout.prop(self, "text", "Select Text")
        #    layout.prop(self,"file","File") external file, TODO
            layout.prop(self, 'textmode', 'textmode', expand=True)
            if self.textmode == 'CSV':
                layout.prop(self, 'csv_header', 'Header fields')
                layout.prop(self, 'csv_dialect', 'Dialect')
                if self.csv_dialect == 'user':
                    layout.label(text="Delimiter")
                    layout.prop(self, 'csv_delimiter', "Delimiter", expand=True)
                    if self.csv_delimiter == 'CUSTOM':
                        layout.prop(self, 'csv_custom_delimiter', "Custom")

                    layout.label(text="Decimalmark")
                    layout.prop(self, 'csv_decimalmark', "Decimalmark", expand=True)
                    if self.csv_decimalmark == 'CUSTOM':
                        layout.prop(self, 'csv_custom_decimalmark', "Custom")

            if self.textmode == 'SV':
                layout.label(text="Select data type")
                layout.prop(self, 'socket_type', expand=True)

            if self.textmode == 'JSON':  # self documenting format
                pass

            layout.operator('node.sverchok_generic_callback', text='Load').fn_name = 'load'

    def copy(self, node):
        self.n_id = ''

    # free potentially lots of data
    def free(self):
        n_id = node_id(self)
        self.csv_data.pop(n_id, None)
        self.list_data.pop(n_id, None)
        self.json_data.pop(n_id, None)

    # dispatch functions
    # general reload should ONLY be called from operator on ui change

    def reload(self):
        if self.textmode == 'CSV':
            self.reload_csv()
        elif self.textmode == 'SV':
            self.reload_sv()
        elif self.textmode == 'JSON':
            self.reload_json()
        # if we turn on reload on update we need a safety check for this
        # two work.
        updateNode(self, None)

    def update(self):  # dispatch based on mode
        # startup safety net
        try:
            l = bpy.data.node_groups[self.id_data.name]
        except Exception as e:
            print(self.name, "cannot run during startup, press update.")
            return

        if not self.current_text:
            return

        if self.textmode == 'CSV':
            self.update_csv()
        elif self.textmode == 'SV':
            self.update_sv()
        elif self.textmode == 'JSON':
            self.update_json()

    def reset(self):
        n_id = node_id(self)
        self.outputs.clear()
        self.current_text = ''
        self.csv_data.pop(n_id, None)
        self.list_data.pop(n_id, None)
        self.json_data.pop(n_id, None)

    def load(self):
        if self.textmode == 'CSV':
            self.load_csv()
        elif self.textmode == 'SV':
            self.load_sv()
        elif self.textmode == 'JSON':
            self.load_json()

    def update_socket(self, context):
        self.update()
    #
    # CSV methods.
    #

    def update_csv(self):
        n_id = node_id(self)

        if self.reload_on_update:
            self.reload_csv()

        if self.current_text and n_id not in self.csv_data:
            self.reload_csv()

            if n_id not in self.csv_data:
                print("CSV auto reload failed, press update")
                self.use_custom_color = True
                self.color = FAIL_COLOR
                return

        self.use_custom_color = True
        self.color = READY_COLOR
        csv_data = self.csv_data[n_id]
        for name in csv_data.keys():
            if name in self.outputs and self.outputs[name].links:
                SvSetSocketAnyType(self, name, [csv_data[name]])

    def reload_csv(self):
        n_id = node_id(self)
        self.load_csv_data()
        #if n_id in self.csv_data:
        #    for i, name in enumerate(self.csv_data[node_id(self)]):
        #        if not name in self.outputs:
        #            self.outputs.new('StringsSocket', name, name)

    def load_csv(self):
        n_id = node_id(self)
        self.load_csv_data()

        for name in self.csv_data[n_id]:
            self.outputs.new('StringsSocket', name, name)

    def load_csv_data(self):
        n_id = node_id(self)

        csv_data = collections.OrderedDict()

        if n_id in self.csv_data:
            del self.csv_data[n_id]

        f = io.StringIO(bpy.data.texts[self.text].as_string())

        # setup CSV options

        if self.csv_dialect == 'user':
            if self.csv_delimiter == 'CUSTOM':
                d = self.csv_custom_delimiter
            else:
                d = self.csv_delimiter

            reader = csv.reader(f, delimiter=d)
        elif self.csv_dialect == 'semicolon':
            self.csv_decimalmark = ','
            reader = csv.reader(f, delimiter=';')
        else:
            reader = csv.reader(f, dialect=self.csv_dialect)
            self.csv_decimalmark = '.'

        # setup parse decimalmark

        if self.csv_decimalmark == ',':
            get_number = lambda s: float(s.replace(',', '.'))
        elif self.csv_decimalmark == 'LOCALE':
            get_number = lambda s: locale.atof(s)
        elif self.csv_decimalmark == 'CUSTOM':
            if self.csv_custom_decimalmark:
                get_number = lambda s: float(s.replace(self.csv_custom_decimalmark, '.'))
        else:  # . default
            get_number = float

    # load data
        for i, row in enumerate(reader):
            if i == 0:  # setup names
                if self.csv_header:
                    for name in row:
                        tmp = name
                        c = 1
                        while tmp in csv_data:
                            tmp = name+str(c)
                            c += 1
                        csv_data[str(tmp)] = []
                    continue  # first row is names
                else:
                    for j in range(len(row)):
                        csv_data["Col "+str(j)] = []
            # load data

            for j, name in enumerate(csv_data):
                try:
                    n = get_number(row[j])
                    csv_data[name].append(n)
                except (ValueError, IndexError):
                    pass  # discard strings other than first row

        if csv_data:
            # check for actual data otherwise fail.
            if not csv_data[list(csv_data.keys())[0]]:
                return
            self.current_text = self.text
            self.csv_data[n_id] = csv_data


#
# Sverchok list data
#
# loads a python list using eval
# any python list is considered valid input and you
# have know which socket to use it with.

    def load_sv(self):
        n_id = node_id(self)

        self.load_sv_data()

        if n_id in self.list_data:
            name_dict = {'m': 'Matrix', 's': 'Data', 'v': 'Vertices'}
            typ = self.socket_type
            new_output_socket(self, name_dict[typ], typ)

    def reload_sv(self):
        self.load_sv_data()

    def load_sv_data(self):
        data = None
        n_id = node_id(self)

        if n_id in self.list_data:
            del self.list_data[n_id]

        f = bpy.data.texts[self.text].as_string()
        # should be able to select external file
        try:
            data = ast.literal_eval(f)
        except:
            pass
        if isinstance(data, list):
            self.list_data[n_id] = data
            self.use_custom_color = True
            self.color = READY_COLOR
            self.current_text = self.text
        else:
            self.use_custom_color = True
            self.color = FAIL_COLOR

    def update_sv(self):
        n_id = node_id(self)

        if self.reload_on_update:
            self.reload_sv()
        # nothing loaded, try to load and if it doesn't work fail
        if n_id not in self.list_data and self.current_text:
            self.reload_sv()

        if n_id not in self.list_data:
            self.use_custom_color = True
            self.color = FAIL_COLOR
            return

        # load data into selected socket
        for item in ['Vertices', 'Data', 'Matrix']:
            if item in self.outputs and self.outputs[item].links:
                SvSetSocketAnyType(self, item, self.list_data[n_id])
#
# JSON
#
# Loads JSON data
#
# format dict {socket_name : (socket type in {'v','m','s'", list data)
#              socket_name1 :etc.
# socket_name must be unique

    def load_json(self):
        n_id = node_id(self)
        self.load_json_data()
        json_data = self.json_data.get(n_id, [])
        if not json_data:
            self.current_text = ''
            return

        for item, data in json_data.items():
            if len(data) == 2 and data[0] in {'v', 's', 'm'}:
                new_output_socket(self, item, data[0])
            else:
                self.use_custom_color = True
                self.color = FAIL_COLOR
                return

    def reload_json(self):
        n_id = node_id(self)
        self.load_json_data()
        if n_id in self.json_data:
            self.use_custom_color = True
            self.color = READY_COLOR

    def load_json_data(self):
        json_data = {}
        n_id = node_id(self)
        # reset data
        if n_id in self.json_data:
            del self.json_data[n_id]

        f = io.StringIO(bpy.data.texts[self.text].as_string())
        try:
            json_data = json.load(f)
        except:
            print("Failed to load JSON data")

        if not json_data:
            self.use_custom_color = True
            self.color = FAIL_COLOR
            return

        self.current_text = self.text
        self.json_data[n_id] = json_data

    def update_json(self):
        n_id = node_id(self)

        if self.reload_on_update:
            self.reload_csv()

        if n_id not in self.json_data and self.current_text:
            self.reload_json()

        if n_id not in self.json_data:
            self.use_custom_color = True
            self.color = FAIL_COLOR
            return

        self.use_custom_color = True
        self.color = READY_COLOR
        json_data = self.json_data[n_id]
        for item in json_data:
            if item in self.outputs and self.outputs[item].links:
                out = json_data[item][1]
                SvSetSocketAnyType(self, item, out)


###############################################################################
#
# Text Output
#
###############################################################################


class SvTextOutNode(bpy.types.Node, SverchCustomTreeNode):
    ''' Text Output Node '''
    bl_idname = 'SvTextOutNode'
    bl_label = 'Text Output'
    bl_icon = 'OUTLINER_OB_EMPTY'

    def avail_texts(self, context):
        texts = bpy.data.texts
        items = [(t.name, t.name, "") for t in texts]
        return items

    def change_mode(self, context):
        self.inputs.clear()

        if self.text_mode == 'CSV':
            self.inputs.new('StringsSocket', 'Col 0', 'Col 0')
            self.base_name = 'Col '
        if self.text_mode == 'JSON':
            self.inputs.new('StringsSocket', 'Data 0', 'Data 0')
            self.base_name = 'Data '
        if self.text_mode == 'SV':
            self.inputs.new('StringsSocket', 'Data', 'Data')

    text = EnumProperty(items=avail_texts, name="Texts",
                        description="Choose text to load", update=updateNode)

    text_modes = [("CSV",   "Csv",      "Csv data", "",  1),
                  ("SV",    "Sverchok", "Python data",  2),
                  ("JSON",  "JSON",     "Sverchok JSON", 3)]

    text_mode = EnumProperty(items=text_modes, default='CSV', update=change_mode)

    # csv options
    csv_dialects = [('excel',      'Excel',        'Standard excel',   1),
                    ('excel-tab',  'Excel tabs',   'Excel tab format', 2),
                    ('unix',       'Unix',         'Unix standard',    3), ]

    csv_dialect = EnumProperty(items=csv_dialects, default='excel')

    # sv options
    sv_modes = [('compact',     'Compact',      'Using str()', 1),
                ('pretty',      'Pretty',       'Using pretty print', 2)]
    sv_mode = EnumProperty(items=sv_modes, default='compact')
    # json options
    json_modes = [('compact',    'Compact',      'Minimal', 1),
                  ('pretty',      'Pretty',      'Indent and order', 2)]
    json_mode = EnumProperty(items=json_modes, default='pretty')

    base_name = StringProperty(name='base_name', default='Col ')
    multi_socket_type = StringProperty(name='multi_socket_type', default='StringsSocket')

    append = BoolProperty(default=False, description="Append to output file")

    # interesting bug dangerous, will think a bit more
    dump_on_update = BoolProperty(default=False, description="Dump file on every update")

    def init(self, context):
        self.inputs.new('StringsSocket', 'Col 0', 'Col 0')

    def draw_buttons(self, context, layout):

        layout.prop(self, 'text', "Select text")

        layout.label("Select output format")
        layout.prop(self, 'text_mode', "Text format", expand=True)

        if self.text_mode == 'CSV':
            layout.prop(self, 'csv_dialect', "Dialect")

        if self.text_mode == 'SV':
            layout.prop(self, 'sv_mode', "Format", expand=True)

        if self.text_mode == 'JSON':
            layout.prop(self, 'json_mode', "Format", expand=True)

        layout.operator('node.sverchok_generic_callback', text='Dump').fn_name = 'dump'
        layout.prop(self, 'append', "Append")
        #layout.prop(self,'dump_on_update', "Dump on every update")

    def update_socket(self, context):
        self.update()

    # manage sockets
    # does not do anything with data until dump is executed

    def update(self):
        if self.text_mode == 'CSV' or self.text_mode == 'JSON':
            multi_socket(self, min=1)
        elif self.text_mode == 'SV':
            pass  # only one input, do nothing
        if self.dump_on_update:
            self.dump()

    # build a string with data from sockets
    def dump(self):
        out = self.get_data()
        if len(out) == 0:
            return False
        if not self.append:
            bpy.data.texts[self.text].clear()
        bpy.data.texts[self.text].write(out)
        self.color = READY_COLOR
        return True

    def get_data(self):
        out = ""
        if self.text_mode == 'CSV':
            data_out = []
            for socket in self.inputs:
                if socket.links and \
                   type(socket.links[0].from_socket) == StringsSocket:

                    tmp = SvGetSocketAnyType(self, socket)
                    if tmp:
                        # flatten list
                        data_out.append(list(itertools.chain.from_iterable(tmp)))

            csv_str = io.StringIO()
            writer = csv.writer(csv_str, dialect=self.csv_dialect)
            for row in zip(*data_out):
                writer.writerow(row)

            out = csv_str.getvalue()

        elif self.text_mode == 'JSON':
            data_out = {}
            name_dict = {'m': 'Matrix', 's': 'Data', 'v': 'Vertices'}

            for socket in self.inputs:
                if socket.links:
                    tmp = SvGetSocketAnyType(self, socket)
                    if tmp:
                        tmp_name = socket.links[0].from_node.name+':'+socket.links[0].from_socket.name
                        name = tmp_name
                        j = 1
                        while name in data_out:  # unique names for json
                            name = tmp_name+str(j)
                            j += 1

                        data_out[name] = (get_socket_type(self, socket.name), tmp)

            if self.json_mode == 'pretty':
                out = json.dumps(data_out, indent=4)
            else:  # compact
                out = json.dumps(data_out, separators=(',', ':'))

        elif self.text_mode == 'SV':
            if self.inputs['Data'].links:
                data = SvGetSocketAnyType(self, self.inputs['Data'])
                if self.sv_mode == 'pretty':
                    out = pprint.pformat(data)
                else:  # compact
                    out = str(data)
        return out


def register():
    bpy.utils.register_class(SvTextInOp)
    bpy.utils.register_class(SvTextInNode)
    bpy.utils.register_class(SvTextOutNode)


def unregister():
    bpy.utils.unregister_class(SvTextInOp)
    bpy.utils.unregister_class(SvTextInNode)
    bpy.utils.unregister_class(SvTextOutNode)

if __name__ == '__main__':
    register()
