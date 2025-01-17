Surface from Boundary Curves
============================

Functionality
-------------

This node generates a Surface object from exactly four Curve object, that
define the boundary of the surface. For example, it can build a plane square
from four edges of that square.

It is assumed that curves provided have the following properties:

* They meet exactly at the corner points of the surface.
* Their directions are orgainized so that the four curves build a cycle (either
  clockwise or counterclockwise).

That is, the second curve must begin at the point where the first curve ends;
and the third curve must begin at the point where the second curve ends; and so
on.

It is also possible to omit the fourth curve, thus to build a surface from
three boundary curves. If the third curve does not end in the same point where
the first curve started, the node will use a straight line segment as fourth
curve.

The surface is calculated as a Coons patch, see https://en.wikipedia.org/wiki/Coons_patch.

When all provided curves are NURBS or NURBS-like, then the node will try to
output NURBS surface. The sufficient requirement for this is that opposite
curves have equal degree. If it is not possible to make a NURBS surface, the
node will create a generic Coons surface.

Surface domain: from 0 to 1 in both directions.

Inputs
------

This node has the following inputs:

* **Curves**. The list of curves to build a surface form. This input can accept
  data with nesting level of 1 or 2 (list of curves or list of lists of
  curves). Each list of curves must have length of 3 or 4. This input is available
  and mandatory only if **Input** parameter is set to **List of Curves**.
* **Curve1**, **Curve2**, **Curve3**, **Curve4**. Curves to build surface from.
  These inputs can accept data with nesting level 1 only (list of curves).
  These inputs are available only if **Input** parameter is set
  to **4 Curves**. Inputs **Curve1**, **Curve2** and **Curve3** are mandatory.
  **Curve4** input is optional.

Parameters
----------

This node has the following parameters:

* **Input**. This defines how the curves are provided. The following options are available:

  * **List of curves**. All curves are provided in a single input **Curves**.
  * **Separate inputs**. Each curve is provided in separate input **Curve1** - **Curve4**.

  The default value is **List of Curves**.

* **Check coincidence**. If enabled, then the node will check that the end
  points of curves being used do actually coincide (within threshold).
  If they do not, the node will give an error (become red), and the processing
  will stop. If this parameter is not enabled, then the node will do not check
  and will just assume that you've ensured the coincidence by yourself somehow
  (for example, you know that from the way you generated the curves). If the
  ends of curves do not coincide, the generated surface may be weird.
* **Max distance**. Maximum distance between end points of the curves, which is
  allowable to decide that they actually coincide. The default value is 0.001.
  This parameter is only available if **Check coincidence** parameter is
  enabled.
* **NURBS option**. This defines whether the node will generate a NURBS surface
  or a generic Surface object. The available options are:

   * **Generic**. Always create a generic Surface object.
   * **Always NURBS**. Create a NURBS surface. If input curves are not NURBS or
     NURBS-like, or if it is not possible to generate a NURBS surface for some
     another reason, the node will fail.
   * **NURBS if possible**. Create a NURBS surface. If input curves are not NURBS or
     NURBS-like, or if it is not possible to generate a NURBS surface for some
     another reason, the node will create a generic Surface object.

   The default option is **NURBS if possible**.

Outputs
-------

This node has the following output:

* **Surface**. The generated surface.

Examples of usage
-----------------

Build four curves and generate a Coons patch from them:

.. image:: https://user-images.githubusercontent.com/284644/82479763-3f1c4c80-9aec-11ea-9a60-f01f0f9e1fa5.png

Similar example with "filleted polylines" as curves instead of cubic splines:

.. image:: https://user-images.githubusercontent.com/284644/82479766-404d7980-9aec-11ea-919b-50616556b5d6.png

One may use such surface to generate another topology:

.. image:: https://user-images.githubusercontent.com/284644/82479764-3fb4e300-9aec-11ea-8ddf-e4fce21f57a2.png

It is possible to use the node together with "Split Curve" node to generate a surface from one closed curve:

.. image:: https://user-images.githubusercontent.com/284644/82479760-3deb1f80-9aec-11ea-8411-22ffd273259f.png

It is possible to use only three boundary curves:

.. image:: https://user-images.githubusercontent.com/284644/210209607-113759b7-9992-4e5d-870d-6aa6dafe0c32.png

If the third curve end does not coincide with the beginning of the first curve,
the node will close the cycle with a straight line segment:

.. image:: https://user-images.githubusercontent.com/284644/210209611-052c63b6-ef39-4c12-a047-d7d369f3469c.png

