# This file is part of project Sverchok. It's copyrighted by the contributors
# recorded in the version control history of the file, available from
# its original location https://github.com/nortikin/sverchok/commit/master
#  
# SPDX-License-Identifier: GPL3
# License-Filename: LICENSE

import numpy as np

from sverchok.utils.logging import info, debug
from sverchok.utils.nurbs_common import from_homogenous
from sverchok.utils.curve import knotvector as sv_knotvector
from sverchok.utils.curve.core import UnsupportedCurveTypeException
from sverchok.utils.curve.nurbs import SvNurbsCurve
from sverchok.utils.curve.algorithms import reverse_curve, reparametrize_curve, unify_curves_degree
from sverchok.utils.curve.nurbs_algorithms import unify_curves, unify_two_curves
from sverchok.utils.surface.core import SvSurface
from sverchok.utils.surface.nurbs import SvNurbsSurface
from sverchok.utils.surface.algorithms import SvCurveLerpSurface, unify_nurbs_surfaces

class SvCoonsSurface(SvSurface):
    __description__ = "Coons Patch"
    def __init__(self, curve1, curve2, curve3, curve4):
        curve1 = reparametrize_curve(curve1)
        curve2 = reparametrize_curve(curve2)
        curve3 = reparametrize_curve(curve3)
        curve4 = reparametrize_curve(curve4)
        self.curve1 = curve1
        self.curve2 = curve2
        self.curve3 = curve3
        self.curve4 = curve4
        self.linear1 = SvCurveLerpSurface.build(curve1, reverse_curve(curve3))
        self.linear2 = SvCurveLerpSurface.build(curve2, reverse_curve(curve4))
        self.c1_t_min, self.c1_t_max = curve1.get_u_bounds()
        self.c3_t_min, self.c3_t_max = curve3.get_u_bounds()

        self.corner1 = self.curve1.evaluate(self.c1_t_min)
        self.corner2 = self.curve1.evaluate(self.c1_t_max)
        self.corner3 = self.curve3.evaluate(self.c3_t_max)
        self.corner4 = self.curve3.evaluate(self.c3_t_min)

        self.normal_delta = 0.001
    
    def get_u_min(self):
        return 0
    
    def get_u_max(self):
        return 1
    
    def get_v_min(self):
        return 0
    
    def get_v_max(self):
        return 1

    def _calc_b(self, u, v, is_array):
        corner1, corner2, corner3, corner4 = self.corner1, self.corner2, self.corner3, self.corner4
        if is_array:
            u = u[np.newaxis].T
            v = v[np.newaxis].T
        b = (corner1 * (1 - u) * (1 - v) + corner2 * u * (1 - v) + corner3 * (1 - u) * v + corner4 * u * v)
        return b
    
    def evaluate(self, u, v):    
        return self.linear1.evaluate(1-u, 1-v) + self.linear2.evaluate(1-v, u) - self._calc_b(1-u, 1-v, False)
    
    def evaluate_array(self, us, vs):
        return self.linear1.evaluate_array(1-us, 1-vs) + self.linear2.evaluate_array(1-vs, us) - self._calc_b(1-us, 1-vs, True)

GENERIC = 'GENERIC'
NURBS_ONLY = 'NURBS'
NURBS_IF_POSSIBLE = 'NURBS_OPTION'

def coons_surface(curve1, curve2, curve3, curve4, use_nurbs=NURBS_IF_POSSIBLE):
    curves = [curve1, curve2, curve3, curve4]
    nurbs_curves = [SvNurbsCurve.to_nurbs(c) for c in curves]
    if use_nurbs == GENERIC:
        return SvCoonsSurface(*curves)
    if any(c is None for c in nurbs_curves):
        if use_nurbs == NURBS_ONLY:
            raise UnsupportedCurveTypeException("Some of curves are not NURBS")
        else:
            return SvCoonsSurface(*curves)
    try:
        nurbs_curves = [c.reparametrize(0,1) for c in nurbs_curves]
        implementation = nurbs_curves[0].get_nurbs_implementation()

        nurbs_curves[0], nurbs_curves[2] = unify_curves_degree([nurbs_curves[0], nurbs_curves[2]])
        nurbs_curves[0], nurbs_curves[2] = unify_curves([nurbs_curves[0], nurbs_curves[2]])
        nurbs_curves[1], nurbs_curves[3] = unify_curves_degree([nurbs_curves[1], nurbs_curves[3]])
        nurbs_curves[1], nurbs_curves[3] = unify_curves([nurbs_curves[1], nurbs_curves[3]])

        degree_u = nurbs_curves[0].get_degree()
        degree_v = nurbs_curves[1].get_degree()

        nurbs_curves[0] = reverse_curve(nurbs_curves[0])
        nurbs_curves[3] = reverse_curve(nurbs_curves[3])

        ruled1 = nurbs_curves[0].make_ruled_surface(nurbs_curves[2], 0, 1)
        ruled2 = nurbs_curves[1].make_ruled_surface(nurbs_curves[3], 0, 1).swap_uv()

        linear_kv = sv_knotvector.generate(1, 2)

        c1_t_min, c1_t_max = nurbs_curves[0].get_u_bounds()
        c3_t_min, c3_t_max = nurbs_curves[2].get_u_bounds()

        pt1 = nurbs_curves[0].evaluate(c1_t_min)
        pt2 = nurbs_curves[0].evaluate(c1_t_max)
        pt3 = nurbs_curves[2].evaluate(c3_t_min)
        pt4 = nurbs_curves[2].evaluate(c3_t_max)

        w1 = nurbs_curves[0].get_weights()[0]
        w2 = nurbs_curves[0].get_weights()[-1]
        w3 = nurbs_curves[2].get_weights()[0]
        w4 = nurbs_curves[2].get_weights()[-1]

        linear_pts = np.array([[pt1,pt3], [pt2,pt4]])
        linear_weights = np.array([[w1,w3], [w2,w4]])
        #linear_weights = np.array([[1,1], [1,1]])
        bilinear = SvNurbsSurface.build(implementation,
                    1, 1,
                    linear_kv, linear_kv,
                    linear_pts, linear_weights)

        ruled1, ruled2, bilinear = unify_nurbs_surfaces([ruled1, ruled2, bilinear])
        knotvector_u = ruled1.get_knotvector_u()
        knotvector_v = ruled1.get_knotvector_v()

        control_points = ruled1.get_control_points() + ruled2.get_control_points() - bilinear.get_control_points()
        weights = ruled1.get_weights() + ruled2.get_weights() - bilinear.get_weights()
        result = SvNurbsSurface.build(implementation,
                    degree_u, degree_v,
                    knotvector_u, knotvector_v,
                    control_points, weights)
        return result
    except UnsupportedCurveTypeException as e:
        if use_nurbs == NURBS_ONLY:
            raise
        else:
            info("Can't create a native Coons surface from curves %s: %s", curves, e)
            return SvCoonsSurface(*curves)

