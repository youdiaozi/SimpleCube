"""
约束由 Message.MSG_DESCRIPTION_VALIDATE 和 SetHandle 共同约束
效果类似cube，即：拖动handle可约束，但直接调整len.X的数值时，无法约束，会自动压小fillet radius

优化：
    1)添加dofillet handle并平滑切换
    2)无论dofillet.on/off，都对fillet radius约束
    3)添加segments handle，并附加起始和结束位置的标记竖线
    4)segments handle及线使用自定义画笔颜色

如何非线性双向变化??
SIMPLECUBE_SEP 实际上没有处理?

如何在draw subx handle时，利用BaseDraw.DrawHUDText() 画对应数字？三维点map to screen？
mousedrag.MouseDragStart：https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d.gui/EditorWindow/index.html?highlight=mouse#EditorWindow.MouseDrag
GetCamera:https://developers.maxon.net/docs/Cinema4DPythonSDK/html/misc/cookbook.html
ViewportSelect.GetPixelInfoPoint(x, y):https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d.utils/ViewportSelect/index.html?highlight=screen#ViewportSelect.GetPixelInfoPoint
projection： https://developers.maxon.net/docs/Cinema4DPythonSDK/html/modules/c4d/C4DAtom/GeListNode/BaseList2D/BaseView/index.html#BaseView.GetProjection
"""

import c4d
import os
import math
import sys
from c4d import plugins, utils, bitmaps, gui

# Be sure to use a unique ID obtained from www.plugincafe.com
PLUGIN_ID = 1053307

# ??c4d的内置c4d_VECTOR_X = 1000怎么回事
c4d_VECTOR_X = 0
c4d_VECTOR_Y = 1
c4d_VECTOR_Z = 2

# 0.5pi
pi05 = 1.570796326


class SimpleCube(plugins.ObjectData):

     # 7 = 主轴(3) + segments handle(3) + dofillet handle(1) ，未算动态的filletradius handle
    HANDLECOUNT = 7
    
    # 用于控制dofillet handle的Y轴增量系数，
    # 注意：dofilletFactor是按self.dofilletFactorA和self.dofilletFactorB之间的比例，
    # 而不是self.dofilletFactorA所代表的比例
    dofilletFactor = 0.0
    # A B 只是控制factor的两端，数值随意（相对于Y轴长度一定比例）
    dofilletFactorA = 0.25
    dofilletFactorB = 0.5
    
    # 用于控制segments handle的各轴增量系数的两端，数值随意（相对于对应轴长度一定比例）
    subFactorA = 0.6
    subFactorB = 0.8      
    
    # segments handle的线的颜色
    subHandleLineColor = c4d.Vector(236/255.0, 105/255.0, 65/255.0)

    # Enable few optimizations, take a look at the GetVirtualObjects method for more information.
    def __init__(self):
        # 利用缓存自动优化，以避免每帧都调用GetVirtualObjects()重新创建对象
        self.SetOptimizeCache(True)

    # Override method, called when the object is initialized to set default values.
    def Init(self, op):
        self.InitAttr(op, c4d.Vector, [c4d.SIMPLECUBE_LEN])
        self.InitAttr(op, int, [c4d.SIMPLECUBE_SUBX])
        self.InitAttr(op, int, [c4d.SIMPLECUBE_SUBY])
        self.InitAttr(op, int, [c4d.SIMPLECUBE_SUBZ])
        self.InitAttr(op, bool, [c4d.SIMPLECUBE_SEP])
        self.InitAttr(op, bool, [c4d.SIMPLECUBE_DOFILLET])
        self.InitAttr(op, float, [c4d.SIMPLECUBE_FRAD])
        self.InitAttr(op, int, [c4d.SIMPLECUBE_SUBF])        

        op[c4d.SIMPLECUBE_LEN]= c4d.Vector(600.0, 200, 300)
        op[c4d.SIMPLECUBE_SUBX] = 5
        op[c4d.SIMPLECUBE_SUBY] = 3
        op[c4d.SIMPLECUBE_SUBZ] = 4
        op[c4d.SIMPLECUBE_SEP] = False
        op[c4d.SIMPLECUBE_DOFILLET] = True
        op[c4d.SIMPLECUBE_FRAD] = 40.0
        op[c4d.SIMPLECUBE_SUBF] = 5
        
        return True

        
    """
    @for Override method, react to some messages received to react to some event.
    @important 调整handle会有Message，但不会触发Message.MSG_DESCRIPTION_VALIDATE
               调整数值会触发Message.MSG_DESCRIPTION_VALIDATE
    """
    def Message(self, node, type, data):
        # MSG_DESCRIPTION_VALIDATE is called after each parameter change. It allows checking of the input value to correct it if not.
        # 参数有效性验证（范围限制）
        if type == c4d.MSG_DESCRIPTION_VALIDATE:
            len = node[c4d.SIMPLECUBE_LEN]
            if len is not None:
                lenx = len[c4d_VECTOR_X]
                leny = len[c4d_VECTOR_Y]
                lenz = len[c4d_VECTOR_Z]
                halfMinlen = min(lenx, leny, lenz) / 2.0
                
                # 约束fillet radius
                node[c4d.SIMPLECUBE_FRAD] = c4d.utils.ClampValue(node[c4d.SIMPLECUBE_FRAD], 0.0, halfMinlen)
                
                # 约束dofillet在调整数值后dofilletFactor handle没有自动更新
                if node[c4d.SIMPLECUBE_DOFILLET] == True:
                    #self.dofilletFactor = c4d.utils.ClampValue(self.dofilletFactor, 0.75, 1.0)
                    self.dofilletFactor = 1.0
                else:
                    #self.dofilletFactor = c4d.utils.ClampValue(self.dofilletFactor, 0.0, 0.25)
                    self.dofilletFactor = 0.0
                
        # MSH_MENUPREPARE is called when the user presses the Menu entry for this object. It allows to setup our object. In this case, it defines the Phong by adding a Phong Tag to the generator.
        elif type == c4d.MSG_MENUPREPARE:
            node.SetPhong(True, False, c4d.utils.DegToRad(40.0))

        return True
        

    # Override method, should return the number of handle.
    def GetHandleCount(self, op):
        dofillet = op[c4d.SIMPLECUBE_DOFILLET]
        if dofillet == True:        
            return self.HANDLECOUNT + 3
        else:
            return self.HANDLECOUNT

    """
    @for 由对应的segment计算各轴变化后segment handle的位置
    @more 参见CalcSubFromHandlePos()，同步修改
    """
    def CalcHandlePosFromSub(self, halfLenx, subx):
        curve = c4d.SplineData()
        curve.MakeLinearSplineLinear(-1)
        newposx = float(c4d.utils.RangeMap(subx, 1, 50, halfLenx * self.subFactorA, halfLenx * self.subFactorB, True, curve))
        #return c4d.utils.ClampValue(newposx+lenx*subFactorA, lenx*subFactorA, lenx*subFactorB)
        return newposx
    
    """
    @for 由各轴变化后segment handle的位置计算对应的segment
    @more max-output设置为50，则由handle可以设置的最大值为50，但实际上segments可以由数值调整至1000
    @more CalcHandlePosFromSub()需要同步修改
    @?? 如果非线性如何的CalcHandlePosFromSub反过来求newposx
    """
    def CalcSubFromHandlePos(self, halfLenx, newposx):                
        curve = c4d.SplineData()
        curve.MakeLinearSplineLinear(-1)
        subx = int(c4d.utils.RangeMap(newposx, halfLenx * self.subFactorA, halfLenx * self.subFactorB, 1, 50, True, curve))
        #return int(c4d.utils.ClampValue(subx, 1, 1000))
        return subx
        
        
    # Override method, called to know the position of a handle.
    def GetHandle(self, op, i, info):
        len = op[c4d.SIMPLECUBE_LEN]
        if len is None: len = c4d.Vector(200.0)
        
        subx = op[c4d.SIMPLECUBE_SUBX]
        if subx is None: subx = 1
        suby = op[c4d.SIMPLECUBE_SUBY]
        if suby is None: suby = 1
        subz = op[c4d.SIMPLECUBE_SUBZ]
        if subz is None: subz = 1
        
        # sep = op[c4d.SIMPLECUBE_SEP]
        # if sep is None: sep = False
        dofillet = op[c4d.SIMPLECUBE_DOFILLET]
        if dofillet is None: dofillet = False
        filletradius = op[c4d.SIMPLECUBE_FRAD]
        if filletradius is None: filletradius = 40.0
        filletsubdivision = op[c4d.SIMPLECUBE_SUBF]
        if filletsubdivision is None: filletsubdivision = 5
        
        halfLenx = len[c4d_VECTOR_X] / 2.0
        halfLeny = len[c4d_VECTOR_Y] / 2.0
        halfLenz = len[c4d_VECTOR_Z] / 2.0
        
        if i is 0: # 主轴X size
            info.position = c4d.Vector(halfLenx, 0.0, 0.0)
            info.direction = c4d.Vector(1.0, 0.0, 0.0)
        elif i is 1: # 主轴Y size
            info.position = c4d.Vector(0.0, halfLeny, 0.0)
            info.direction = c4d.Vector(0.0, 1.0, 0.0)
        elif i is 2: # 主轴Z size
            info.position = c4d.Vector(0.0, 0.0, halfLenz)
            info.direction = c4d.Vector(0.0, 0.0, 1.0)
        elif i is 7: # X filletradius
            info.position = c4d.Vector(halfLenx, halfLeny - filletradius, halfLenz - filletradius)
            info.direction = c4d.Vector(0.0, -1.0, -1.0).GetNormalized()
        elif i is 8: # Y filletradius
            info.position = c4d.Vector(halfLenx - filletradius, halfLeny, halfLenz - filletradius)
            info.direction = c4d.Vector(-1.0, 0.0, -1.0).GetNormalized()
        elif i is 9: # Z filletradius
            info.position = c4d.Vector(halfLenx - filletradius, halfLeny - filletradius, halfLenz)
            info.direction = c4d.Vector(-1.0, -1.0, 0.0).GetNormalized()
            
        if i is 3: # X segments handle
            temppos = self.CalcHandlePosFromSub(halfLenx, subx)
            info.position = c4d.Vector(temppos, 0.0, 0.0)
            info.direction = c4d.Vector(1.0, 0.0, 0.0)
        elif i is 4: # Y segments handle
            temppos = self.CalcHandlePosFromSub(halfLeny, suby)
            info.position = c4d.Vector(0.0, temppos, 0.0)
            info.direction = c4d.Vector(0.0, 1.0, 0.0)
        elif i is 5: # Z segments handle
            temppos = self.CalcHandlePosFromSub(halfLenz, subz)
            info.position = c4d.Vector(0.0, 0.0, temppos)
            info.direction = c4d.Vector(0.0, 0.0, 1.0)
        elif i is 6: # dofillet handle
            if dofillet == True:
                self.dofilletFactor = c4d.utils.ClampValue(self.dofilletFactor, 0.5, 1.0)
            else:
                self.dofilletFactor = c4d.utils.ClampValue(self.dofilletFactor, 0.0, 0.49)
            
            info.position = c4d.Vector(halfLenx, halfLeny * ((1+self.dofilletFactorA) + (self.dofilletFactorB-self.dofilletFactorA) * self.dofilletFactor), halfLenz)
            info.direction = c4d.Vector(0.0, 1.0, 0.0)
        
        info.type = c4d.HANDLECONSTRAINTTYPE_LINEAR


    """
    @for Override method, called when the user moves a handle. This is the place to set parameters.
    @important 约束，调整handle时也自动调整filletradius
    """    
    def SetHandle(self, op, i, p, info):
        data = op.GetDataInstance()
        if data is None: return
        
        len = c4d.Vector()
        len = op[c4d.SIMPLECUBE_LEN]
        if len is None: return
        
        halfLenx = len[c4d_VECTOR_X] / 2.0
        halfLeny = len[c4d_VECTOR_Y] / 2.0
        halfLenz = len[c4d_VECTOR_Z] / 2.0
        
        halfMinlen = 0.0
        if op[c4d.SIMPLECUBE_DOFILLET] == True:
            halfMinlen = op[c4d.SIMPLECUBE_FRAD]
        
        tmp = c4d.HandleInfo()
        self.GetHandle(op, i, tmp)
        
        val = (p - tmp.position) * info.direction

        if i is 0:
            halfLenx = utils.FCut(halfLenx + val, halfMinlen, sys.maxint)
        elif i is 1:
            halfLeny = utils.FCut(halfLeny + val, halfMinlen, sys.maxint)
        elif i is 2:
            halfLenz = utils.FCut(halfLenz + val, halfMinlen, sys.maxint)
        # 主轴XYZ handle
        # @important: op[c4d.SIMPLECUBE_LEN]是值传递，不是引用，不能单独各项赋值
        if i is 0 or i is 1 or i is 2:
            op[c4d.SIMPLECUBE_LEN] = c4d.Vector(halfLenx*2.0, halfLeny*2.0, halfLenz*2.0)
            
            # !重新约束（在标准的cube，这步是在Fillet.checked修改后再约束的）
            halfMinlen = min(halfLenx, halfLeny, halfLenz)
            op[c4d.SIMPLECUBE_FRAD] = c4d.utils.ClampValue(op[c4d.SIMPLECUBE_FRAD], 0.0, halfMinlen)
        
        # XYZ filletradius handle
        if i is 7 or i is 8 or i is 9:
            halfMinlen = min(halfLenx, halfLeny, halfLenz)
            op[c4d.SIMPLECUBE_FRAD] = utils.FCut(op[c4d.SIMPLECUBE_FRAD] + val, 0.0, halfMinlen)
            
        # XYZ segments factor
        if i is 3 or i is 4 or i is 5:
            if i is 3:
                op[c4d.SIMPLECUBE_SUBX] = self.CalcSubFromHandlePos(halfLenx, p[0])
            elif i is 4:
                op[c4d.SIMPLECUBE_SUBY] = self.CalcSubFromHandlePos(halfLeny, p[1])
            elif i is 5:
                op[c4d.SIMPLECUBE_SUBZ] = self.CalcSubFromHandlePos(halfLenz, p[2])
                
        # dofillet handle
        if i is 6:
            if halfLeny > 0:
                dofilletHandlePointY = c4d.utils.ClampValue(p[1], halfLeny * (1+self.dofilletFactorA), halfLeny * (1+self.dofilletFactorB))
                self.dofilletFactor = (dofilletHandlePointY - halfLeny * (1+self.dofilletFactorA)) / (halfLeny * (1+self.dofilletFactorB) - halfLeny * (1+self.dofilletFactorA))
               
                if self.dofilletFactor >= 0.5 and op[c4d.SIMPLECUBE_DOFILLET] == False: # 多于一半，则dofillet.on
                    op[c4d.SIMPLECUBE_DOFILLET] = True
                elif self.dofilletFactor < 0.5 and op[c4d.SIMPLECUBE_DOFILLET] == True: # 少于，则dofillet.off
                    op[c4d.SIMPLECUBE_DOFILLET] = False
    

    # Override method, draw additional stuff in the viewport (e.g. the handles).
    def Draw(self, op, drawpass, bd, bh):
        if drawpass!=c4d.DRAWPASS_HANDLES: return c4d.DRAWRESULT_SKIP

        len = op[c4d.SIMPLECUBE_LEN]
        halfLenx = len[c4d_VECTOR_X] / 2.0
        halfLeny = len[c4d_VECTOR_Y] / 2.0
        halfLenz = len[c4d_VECTOR_Z] / 2.0
        
        subx = op[c4d.SIMPLECUBE_SUBX]
        suby = op[c4d.SIMPLECUBE_SUBY]
        subz = op[c4d.SIMPLECUBE_SUBZ]
        
        dofillet = op[c4d.SIMPLECUBE_DOFILLET]
        filletradius = op[c4d.SIMPLECUBE_FRAD]

        hitid = op.GetHighlightHandle(bd)
        bd.SetMatrix_Matrix(op, bh.GetMg()) # 设置坐标为对象所在3d空间坐标
        
        for i in xrange(self.GetHandleCount(op)):
            if i == hitid:
                bd.SetPen(c4d.GetViewColor(c4d.VIEWCOLOR_SELECTION_PREVIEW))
            else:
                if i is 3 or i is 4 or i is 5: # segments handle使用自定义颜色
                    bd.SetPen(self.subHandleLineColor)
                else: # 其它默认设置
                    bd.SetPen(c4d.GetViewColor(c4d.VIEWCOLOR_ACTIVEPOINT))
                
            # 画handle圆点
            info = c4d.HandleInfo()
            self.GetHandle(op, i, info)
            bd.DrawHandle(info.position, c4d.DRAWHANDLE_BIG, 0)

            bd.SetPen(c4d.GetViewColor(c4d.VIEWCOLOR_ACTIVEPOINT))
            if i is 0 or i is 1 or i is 2:
                bd.DrawLine(info.position, c4d.Vector(), 0)
            elif i is 7 or i is 8 or i is 9:
                bd.DrawLine(info.position, c4d.Vector(halfLenx, halfLeny, halfLenz), 0)
                        
            # segments handle
            if i is 3 or i is 4 or i is 5:
                bd.SetPen(self.subHandleLineColor) # segments handle使用自定义颜色
                #bd.DrawLine(info.position, c4d.Vector(), 0) # 因为不会超过len，所以其实不需要画
                
                halfMinlen = min(halfLenx, halfLeny, halfLenz)
                endfactor = 0.05 # 0.05倍最短边一半的长作为竖线的一半高度
                if i is 3:
                    # 额外的segments handle两端小竖线
                    v1 = c4d.Vector(halfLenx*self.subFactorA, halfMinlen*endfactor, 0)
                    v2 = c4d.Vector(halfLenx*self.subFactorA, -halfMinlen*endfactor, 0)
                    bd.DrawLine(v1, v2, 0)
                    
                    v1 = c4d.Vector(halfLenx*self.subFactorB, halfMinlen*endfactor, 0)
                    v2 = c4d.Vector(halfLenx*self.subFactorB, -halfMinlen*endfactor, 0)
                    bd.DrawLine(v1, v2, 0)
                    
                    # 三维坐标点转二维屏幕点 WorldToScreen（后面是偏移，以避开handle）
                    screenPoint = bd.WS(info.position) + c4d.Vector(30, -30, 0)
                    bd.DrawHUDText(screenPoint.x, screenPoint.y, subx) # 会自动切换到2d平面坐标，所以要切换回3d空间                    
                    bd.SetMatrix_Matrix(op, bh.GetMg()) # 切换回对象所在3d空间坐标
                elif i is 4:
                    # 额外的segments handle两端小竖线
                    v1 = c4d.Vector(0, halfLeny*self.subFactorA, halfMinlen*endfactor)
                    v2 = c4d.Vector(0, halfLeny*self.subFactorA, -halfMinlen*endfactor)
                    bd.DrawLine(v1, v2, 0)
                    
                    v1 = c4d.Vector(0, halfLeny*self.subFactorB, halfMinlen*endfactor)
                    v2 = c4d.Vector(0, halfLeny*self.subFactorB, -halfMinlen*endfactor)
                    bd.DrawLine(v1, v2, 0)
                    
                    # 三维坐标点转二维屏幕点 WorldToScreen（后面是偏移，以避开handle）
                    screenPoint = bd.WS(info.position) + c4d.Vector(30, -30, 0)
                    bd.DrawHUDText(screenPoint.x, screenPoint.y, suby) # 会自动切换到2d平面坐标，所以要切换回3d空间                    
                    bd.SetMatrix_Matrix(op, bh.GetMg()) # 切换回对象所在3d空间坐标
                elif i is 5:
                    # 额外的segments handle两端小竖线
                    v1 = c4d.Vector(halfMinlen*endfactor, 0, halfLenz*self.subFactorA)
                    v2 = c4d.Vector(-halfMinlen*endfactor, 0, halfLenz*self.subFactorA)
                    bd.DrawLine(v1, v2, 0)
                    
                    v1 = c4d.Vector(halfMinlen*endfactor, 0, halfLenz*self.subFactorB)
                    v2 = c4d.Vector(-halfMinlen*endfactor, 0, halfLenz*self.subFactorB)
                    bd.DrawLine(v1, v2, 0)
                    
                    # 三维坐标点转二维屏幕点 WorldToScreen（后面是偏移，以避开handle）
                    screenPoint = bd.WS(info.position) + c4d.Vector(30, -30, 0)
                    bd.DrawHUDText(screenPoint.x, screenPoint.y, subz) # 会自动切换到2d平面坐标，所以要切换回3d空间                    
                    bd.SetMatrix_Matrix(op, bh.GetMg()) # 切换回对象所在3d空间坐标
                
            if i is 6: # dofillet handle
                v1 = c4d.Vector(halfLenx, halfLeny * (1+self.dofilletFactorB), halfLenz)
                v2 = c4d.Vector(halfLenx, halfLeny * (1+self.dofilletFactorA), halfLenz)
                bd.DrawLine(v1, v2, 0)
                
        return c4d.DRAWRESULT_OK
      

    # Override method, should return the bounding box of the generated object.
    # dimension指正轴长
    def GetDimension(self, op, mp, rad):
        len = op[c4d.SIMPLECUBE_LEN]
        if len is None: return

        rad.x = len[c4d_VECTOR_X] / 2.0
        rad.y = len[c4d_VECTOR_Y] / 2.0
        rad.z = len[c4d_VECTOR_Z] / 2.0
    
    """
    @for 计算全部顶点的位置并生成
    """
    def MakePoints(self, obj, parr, lenx, leny, lenz, subx, suby, subz, sep, dofillet, filletradius, filletsubdivision):
        # ==============最底面外围一圈==================
        # -Z平面
        j = 0
        base = 0        
        for i in xrange(base, base+subx):
            tempx = -lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0)
            tempy = -leny/2.0
            tempz = -lenz/2.0+filletradius
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # +X平面
        j = 0
        base = base+subx
        for i in xrange(base, base+subz):
            tempx = -(-lenx/2.0+filletradius)
            tempy = -leny/2.0
            tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # +Z平面
        j = 0
        base = base+subz
        for i in xrange(base, base+subx):
            tempx = -(-lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0))
            tempy = -leny/2.0
            tempz = -(-lenz/2.0+filletradius)
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # -X平面
        j = 0
        base = base+subx
        for i in xrange(base, base+subz):
            tempx = -lenx/2.0+filletradius
            tempy = -leny/2.0
            tempz = -(-lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0))
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        base = base+subz

        # ==============底部弧度沿Y轴由下而上==================        
        for a in xrange(1, filletsubdivision):
            # 得到Y轴弧度的sin、cos的系数
            sn, cs = utils.SinCos(float(a)/filletsubdivision*pi05)
            
            # -Z平面
            j = 0
            base = base+0
            for i in xrange(base, base+subx):
                tempx = -lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0)
                tempy = -leny/2.0+(1-cs)*filletradius
                tempz = -lenz/2.0+(1-sn)*filletradius
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-Z+X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-sn2*sn) # 先投影X轴，再投影Y轴
                tempy = -leny/2.0+(1-cs)*filletradius                
                tempz = -lenz/2.0+filletradius*(1-cs2*sn) # 先投影Z轴，再投影Y轴
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -(-lenx/2.0+(1-sn)*filletradius)
                tempy = -leny/2.0+(1-cs)*filletradius
                tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+X+Z夹角
            j = 0
            base = base+subz
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-cs2*sn)
                tempy = -leny/2.0+(1-cs)*filletradius                
                tempz = lenz/2.0-filletradius*(1-sn2*sn)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +Z平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subx):
                tempx = -(-lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0))
                tempy = -leny/2.0+(1-cs)*filletradius
                tempz = -(-lenz/2.0+(1-sn)*filletradius)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+Z-X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-sn2*sn)
                tempy = -leny/2.0+(1-cs)*filletradius                
                tempz = lenz/2.0-filletradius*(1-cs2*sn)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # -X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -lenx/2.0+(1-sn)*filletradius
                tempy = -leny/2.0+(1-cs)*filletradius
                tempz = -(-lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0))
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-X-Z夹角
            j = 0
            base = base+subz            
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-cs2*sn)
                tempy = -leny/2.0+(1-cs)*filletradius                
                tempz = -lenz/2.0+filletradius*(1-sn2*sn)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1

            # !序号错乱会导致最后一个圆角没有
            base = base+filletsubdivision
        
        # ==============直线部分沿Y轴由下而上==================
        for a in xrange(0, suby+1):                        
            # -Z平面
            j = 0
            base = base+0
            for i in xrange(base, base+subx):
                tempx = -lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0)
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -lenz/2.0
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-Z+X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-sn2) # 先投影X轴，再投影Y轴
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -lenz/2.0+filletradius*(1-cs2) # 先投影Z轴，再投影Y轴
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -(-lenx/2.0)
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+X+Z夹角
            j = 0
            base = base+subz
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-cs2)
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = lenz/2.0-filletradius*(1-sn2)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +Z平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subx):
                tempx = -(-lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0))
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -(-lenz/2.0)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+Z-X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-sn2)
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = lenz/2.0-filletradius*(1-cs2)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # -X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -lenx/2.0
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -(-lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0))
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-X-Z夹角
            j = 0
            base = base+subz
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-cs2)
                tempy = -leny/2.0+filletradius+float(a)/suby*(leny-filletradius*2.0)
                tempz = -lenz/2.0+filletradius*(1-sn2)

                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            base = base+filletsubdivision
        
        # ==============顶部弧度沿Y轴由下而上==================
        for a in xrange(1, filletsubdivision):
            # 得到Y轴弧度的sin、cos的系数
            sn, cs = utils.SinCos(float(a)/filletsubdivision*pi05)
            
            # -Z平面
            j = 0
            base = base+0
            for i in xrange(base, base+subx):
                tempx = -lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0)
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = -lenz/2.0+(1-cs)*filletradius
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-Z+X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-sn2*cs) # 先投影X轴，再投影Y轴
                tempy = leny/2.0-(1-sn)*filletradius                
                tempz = -lenz/2.0+filletradius*(1-cs2*cs) # 先投影Z轴，再投影Y轴
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -(-lenx/2.0+(1-cs)*filletradius)
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+X+Z夹角
            j = 0
            base = base+subz
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = lenx/2.0-filletradius*(1-cs2*cs)
                tempy = leny/2.0-(1-sn)*filletradius                
                tempz = lenz/2.0-filletradius*(1-sn2*cs)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # +Z平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subx):
                tempx = -(-lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0))
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = -(-lenz/2.0+(1-cs)*filletradius)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>+Z-X夹角
            j = 0
            base = base+subx
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-sn2*cs)
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = lenz/2.0-filletradius*(1-cs2*cs)
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # -X平面
            j = 0
            base = base+filletsubdivision
            for i in xrange(base, base+subz):
                tempx = -lenx/2.0+(1-cs)*filletradius
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = -(-lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0))
                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            # >>>-X-Z夹角
            j = 0
            base = base+subz
            for i in xrange(base, base+filletsubdivision):
                # 得到夹角的sin、cos的系数
                sn2, cs2 = utils.SinCos(float(j)/filletsubdivision*pi05)
                
                tempx = -lenx/2.0+filletradius*(1-cs2*cs)
                tempy = leny/2.0-(1-sn)*filletradius
                tempz = -lenz/2.0+filletradius*(1-sn2*cs)

                parr[i] = c4d.Vector(tempx, tempy, tempz)
                j = j+1
                
            base = base+filletsubdivision
        
        # ==============最顶面外围一圈==================        
        # -Z平面
        j = 0
        for i in xrange(base, base+subx):
            tempx = -lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0)
            tempy = leny/2.0
            tempz = -lenz/2.0+filletradius
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # +X平面
        j = 0
        base = base+subx
        for i in xrange(base, base+subz):
            tempx = -(-lenx/2.0+filletradius)
            tempy = leny/2.0
            tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # +Z平面
        j = 0
        base = base+subz
        for i in xrange(base, base+subx):
            tempx = -(-lenx/2.0+filletradius+float(j)/subx*(lenx-filletradius*2.0))
            tempy = leny/2.0
            tempz = -(-lenz/2.0+filletradius)
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        # -X平面
        j = 0
        base = base+subx
        for i in xrange(base, base+subz):
            tempx = -lenx/2.0+filletradius
            tempy = leny/2.0
            tempz = -(-lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0))
            parr[i] = c4d.Vector(tempx, tempy, tempz)
            j = j+1
            
        base = base+subz

        # ==============最顶面中间部分==================        
        for j in xrange(1, subz):
            for i in xrange(1, subx):
                tempx = -lenx/2.0+filletradius+float(i)/subx*(lenx-filletradius*2.0)
                tempy = leny/2.0
                tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
                parr[base+(i-1)+(subx-1)*(j-1)] = c4d.Vector(tempx, tempy, tempz)
                
        base = base+(subx-1)*(subz-1)
        
        # ==============最底面中间部分==================        
        for j in xrange(1, subz):
            for i in xrange(1, subx):
                tempx = -lenx/2.0+filletradius+float(i)/subx*(lenx-filletradius*2.0)
                tempy = -leny/2.0
                tempz = -lenz/2.0+filletradius+float(j)/subz*(lenz-filletradius*2.0)
                parr[base+(i-1)+(subx-1)*(j-1)] = c4d.Vector(tempx, tempy, tempz)
                
        # ==============设置顶点==================
        pcnt = len(parr)
        for i in xrange(pcnt):
            obj.SetPoint(i, parr[i])
            
        
    """
    @for 计算全部多边形的位置并生成
    """
    def MakePolygons(self, obj, parr, lenx, leny, lenz, subx, suby, subz, sep, dofillet, filletradius, filletsubdivision):
        # ==============设置多边形==================
        bottomring = (subx*2+subz*2)
        middlering = (subx*2+subz*2+filletsubdivision*4)
        
        base = 0
        # -Z平面
        for i in xrange(0, subx):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = i
                    b = a+bottomring
                else:
                    a = bottomring+middlering*(j-1)+i
                    b = a+middlering
                    
                c = b+1
                d = a+1                    
                poly = c4d.CPolygon(a,b,c,d)
                obj.SetPolygon(base, poly)

                base = base+1

        # -Z+X夹角
        for i in xrange(0, filletsubdivision):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx
                    b = bottomring+a+i
                    c = b+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+subx+i
                    b = bottomring+middlering*j+subx
                    c = a+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+subx+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                    
                base = base+1
                
        # +X平面
        for i in xrange(0, subz):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx+i
                    b = bottomring+subx+filletsubdivision+i
                    c = b+1
                    d = a+1
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+subx+filletsubdivision+i
                    b = bottomring+middlering*j+subx+i
                    c = b+1
                    d = a+1
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+subx+filletsubdivision+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # +X+Z夹角
        for i in xrange(0, filletsubdivision):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx+subz
                    b = bottomring+subx+filletsubdivision+subz+i
                    c = b+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+subx+filletsubdivision+subz+i
                    b = bottomring+middlering*j+subx+subz
                    c = a+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+subx+filletsubdivision+subz+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # +Z平面
        for i in xrange(0, subx):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx+subz+i
                    b = bottomring+0.5*middlering+i
                    c = b+1
                    d = a+1
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+0.5*middlering+i
                    b = bottomring+middlering*j+subx+subz+i
                    c = b+1
                    d = a+1
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+0.5*middlering+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # +Z-X夹角
        for i in xrange(0, filletsubdivision):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx+subz+subx
                    b = bottomring+0.5*middlering+subx+i
                    c = b+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+i
                    b = bottomring+middlering*j+0.5*bottomring+subx
                    c = a+1
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # -X平面
        for i in xrange(0, subz):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = subx+subz+subx+i
                    b = bottomring+0.5*middlering+subx+filletsubdivision+i
                    c = b+1
                    d = a+1                    
                    if i == subz-1:
                        d = 0 # 起始点所在线
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+filletsubdivision+i
                    b = bottomring+middlering*j+0.5*bottomring+subx+i
                    c = b+1
                    if i == subz-1:
                        c = bottomring+middlering*j # 起始点所在线
                    d = a+1
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+filletsubdivision+i
                    b = a+middlering
                    c = b+1
                    d = a+1                    
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # -X-Z夹角
        for i in xrange(0, filletsubdivision):
            for j in xrange(0, filletsubdivision*2+suby):
                a = b = c = d = 0
                
                if j == 0:
                    a = 0
                    b = bottomring+0.5*middlering+subx+filletsubdivision+subz+i
                    c = b+1
                    if i == filletsubdivision-1:
                        c = bottomring # 起始点所在线
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                elif j == (filletsubdivision*2+suby-1):
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+filletsubdivision+subz+i
                    b = bottomring+middlering*j
                    c = a+1
                    if i == filletsubdivision-1:
                        c = bottomring+middlering*(j-1) # 起始点所在线
                    poly = c4d.CPolygon(a,b,c)
                    obj.SetPolygon(base, poly)
                else:
                    a = bottomring+middlering*(j-1)+0.5*middlering+subx+filletsubdivision+subz+i
                    b = a+middlering
                    c = b+1
                    if i == filletsubdivision-1:
                        c = bottomring+middlering*j # 起始点所在线
                    d = a+1
                    if i == filletsubdivision-1:
                        d = bottomring+middlering*(j-1) # 起始点所在线
                    poly = c4d.CPolygon(a,b,c,d)
                    obj.SetPolygon(base, poly)

                base = base+1
                
        # ==============最顶面中间部分==================
        maxlevel = filletsubdivision*2+suby-1
        topfirst = bottomring+middlering*maxlevel+bottomring
        for j in xrange(0, subz):
            for i in xrange(0, subx):
                a = b = c = d = 0
                # !important：考虑subx=1，即分段只有1段，右边界为顶部外围一圈的情况
                if (subx-1)*(subz-1)>0: # subx subz都>1的情况，正常边界
                    if j == 0:
                        a = bottomring+middlering*maxlevel+i
                        if i == 0:
                            b = topfirst-1
                        else:
                            b = topfirst+(i-1)
                        if i == subx-1:
                            c = bottomring+middlering*maxlevel+subx+1
                        else:
                            c = topfirst+i
                        d = a+1
                    elif j == subz-1:
                        b = bottomring+middlering*maxlevel+subx+subz+subx-i
                        if i == 0:
                            a = b+1
                        else:
                            a = topfirst+(subx-1)*(j-1)+(i-1)
                        c = b-1
                        if i == 0:
                            d = topfirst+(subx-1)*(j-1)
                        elif i == subx-1:
                            d = c-1
                        else:
                            d = a+1
                    else:
                        if i == 0:
                            a = topfirst-1-(j-1)
                            b = a-1
                            d = topfirst+(subx-1)*(j-1)
                            c = d+subx-1
                        elif i == subx-1:
                            a = topfirst+(subx-1)*(j-1)+(i-1)
                            b = a+subx-1
                            d = bottomring+middlering*maxlevel+subx+j
                            c = d+1
                        else:
                            a = topfirst+(subx-1)*(j-1)+(i-1)
                            b = a+subx-1
                            c = b+1
                            d = a+1
                elif ((subx-1) == 0) and ((subz-1) > 0): # 单独subx=1的情况，修正c d（触边界）
                    if j == 0:
                        a = bottomring+middlering*maxlevel
                        b = topfirst-1
                        d = a+1
                        c = d+1
                    elif j == subz-1:
                        b = bottomring+middlering*maxlevel+subx+subz+subx
                        a = b+1
                        c = bottomring+middlering*maxlevel+subx+subz
                        d = c-1
                    else:
                        a = topfirst-j
                        b = a-1
                        d = bottomring+middlering*maxlevel+subx+j
                        c = d+1
                elif ((subz-1) == 0) and ((subx-1) > 0): # 单独subz=1的情况，修正b c（触边界）
                    if i == 0:
                        a = bottomring+middlering*maxlevel
                        b = a+subx+subz+subx  
                        d = a+1
                        c = b-1
                    elif i == subx-1:
                        d = bottomring+middlering*maxlevel+subx
                        a = d-1
                        c = d+subz
                        b = c+1
                    else:
                        a = bottomring+middlering*maxlevel+i
                        d = a+1
                        b = bottomring+middlering*maxlevel+subx+subz+subx-i
                        c = b-1
                elif ((subx-1) == 0) and ((subz-1) == 0): # subx=subz=1的情况，修正b c d（触边界）
                    a = bottomring+middlering*maxlevel
                    d = a+1
                    c = d+1
                    b = c+1
                
                poly = c4d.CPolygon(a,b,c,d)
                obj.SetPolygon(base, poly)
                
                base = base+1
                
        # ==============最底面中间部分==================        
        bottomfirst = topfirst+(subx-1)*(subz-1)
        for j in xrange(0, subz):
            for i in xrange(0, subx):
                a = b = c = d = 0
                
                # !important：考虑subx=1，即分段只有1段，右边界为底部外围一圈的情况
                if (subx-1)*(subz-1)>0: # subx subz都>1的情况，正常边界                
                    if j == 0:
                        b = i
                        if i == 0:
                            a = bottomring-1
                        else:
                            a = bottomfirst+(i-1)
                        c = b+1
                        if i == 0:
                            d = bottomfirst
                        elif i == subx-1:
                            d = c+1
                        else:
                            d = a+1
                    elif j == subz-1:
                        a = subx+subz+subx-i
                        if i == 0:
                            b = a+1
                        else:
                            b = bottomfirst+(subx-1)*(j-1)+(i-1)
                        d = a-1
                        if i == 0:
                            c = bottomfirst+(subx-1)*(j-1)
                        elif i == subx-1:
                            c = d-1
                        else:
                            c = b+1
                    else:
                        if i == 0:
                            b = bottomring-j
                            a = b-1
                            c = bottomfirst+(subx-1)*(j-1)
                            d = c+subx-1
                        elif i == subx-1:
                            b = bottomfirst+(subx-1)*(j-1)+(i-1)
                            a = b+subx-1
                            c = subx+j
                            d = c+1
                        else:
                            b = bottomfirst+(subx-1)*(j-1)+(i-1)
                            a = b+subx-1
                            c = b+1
                            d = a+1
                elif ((subx-1) == 0) and ((subz-1) > 0): # 单独subx=1的情况，修正c d（触边界）
                    if j == 0:
                        b = a
                        c = b+subx
                        d = c+1
                        a = subx+subz+subx+subz-1
                    elif j == subz-1:
                        d = subx+subz
                        c = d-1
                        a = d+subx
                        b = a+1
                    else:
                        c = subx+j
                        d = c+1
                        b = subx+subz+subx+subz-j
                        a = b-1
                elif ((subz-1) == 0) and ((subx-1) > 0): # 单独subz=1的情况，修正c d（触边界）
                    if i == 0:
                        b = 0
                        c = b+1
                        a = subx+subz+subx
                        d = a-1
                    elif i == subx-1:
                        c = subx
                        b = c-1
                        d = c+subz
                        a = d+1
                    else:
                        b = i
                        c = b+1
                        a = subx+subz+subx-i
                        d = a-1
                elif ((subx-1) == 0) and ((subz-1) == 0): # subx=subz=1的情况，修正b c d（触边界）
                    b = 0
                    c = b+1
                    d = c+1
                    a = d+1

                poly = c4d.CPolygon(a,b,c,d)
                obj.SetPolygon(base, poly)
                
                base = base+1
        
    
    """
    @Override
    @for 生成mesh
    """
    def GetVirtualObjects(self, op, hierarchyhelp):
        len = op[c4d.SIMPLECUBE_LEN]
        if len is None: len = c4d.Vector(200.0)
        lenx = len[c4d_VECTOR_X]
        leny = len[c4d_VECTOR_Y]
        lenz = len[c4d_VECTOR_Z]
        
        subx = op[c4d.SIMPLECUBE_SUBX]
        if subx is None: subx = 1
        suby = op[c4d.SIMPLECUBE_SUBY]
        if suby is None: suby = 1
        subz = op[c4d.SIMPLECUBE_SUBZ]
        if subz is None: subz = 1
        
        sep = op[c4d.SIMPLECUBE_SEP]
        if sep is None: sep = False
        
        # fillet
        filletradius = op[c4d.SIMPLECUBE_FRAD]                
        if filletradius is None: filletradius = 40.0
        filletsubdivision = op[c4d.SIMPLECUBE_SUBF]
        if filletsubdivision is None: filletsubdivision = 5
        
        dofillet = op[c4d.SIMPLECUBE_DOFILLET]
        if dofillet is None: dofillet = False
        # !!如果fillet.off，则强制在计算时filletradius=0
        if dofillet == False:
            filletradius = 0.0
            filletsubdivision = 0
        
        # 考虑LOD
        subx = utils.CalcLOD(subx, 1, 1, 1000)
        suby = utils.CalcLOD(suby, 1, 1, 1000)
        subz = utils.CalcLOD(subz, 1, 1, 1000)
        filletsubdivision = utils.CalcLOD(filletsubdivision, 1, 1, 1000)

        i = 0
        sn = 0.0
        cs = 0.0
        
        # 计算全部顶点数(XZ平面顶点数 * Y轴层数 - 底层顶点少的部分 + 上下面内框顶点数)
        pcnt = (subx * 2 + subz * 2 + filletsubdivision * 4) * (suby + 1 + filletsubdivision * 2) - filletsubdivision * 4 * 2 + (subx - 1) * (subz -1) * 2
        parr = [c4d.Vector()]*pcnt
        
        polycnt = (subx * 2 + subz * 2 + filletsubdivision * 4) * (suby + filletsubdivision * 2) + subx * subz * 2
        
        # 创建对象
        obj = c4d.PolygonObject(pcnt, polycnt)
        if obj is None: return None
        
        # 计算全部顶点的位置
        self.MakePoints(obj, parr, lenx, leny, lenz, subx, suby, subz, sep, dofillet, filletradius, filletsubdivision)        
                
        # 计算全部多边形的位置
        self.MakePolygons(obj, parr, lenx, leny, lenz, subx, suby, subz, sep, dofillet, filletradius, filletsubdivision)

        return obj
        
    """
    @for 利用Dofillet参数的值，动态切换其它参数的enabled
    """
    def GetDEnabling(self, node, id, t_data, flags, itemdesc):
        paramId = id[0].id
        
        if node[c4d.SIMPLECUBE_DOFILLET] == True:
            if paramId == c4d.SIMPLECUBE_FRAD or paramId == c4d.SIMPLECUBE_SUBF:
                return True
            elif paramId == c4d.SIMPLECUBE_SEP:
                return False
        elif node[c4d.SIMPLECUBE_DOFILLET] == False:
            if paramId == c4d.SIMPLECUBE_FRAD or paramId == c4d.SIMPLECUBE_SUBF:
                return False
            elif paramId == c4d.SIMPLECUBE_SEP:
                return True
        
        return True
        
        
    """
    @for BubbleHelp，即鼠标指到Objects管理器的对象时，状态栏和冒泡显示的文字
    """
    def GetBubbleHelp(self, node):
        return "Simple Cube --Bubble Help--"


 # This code is called at the startup, it register the class SimpleCube as a plugin to be used later in Cinema 4D. It have to be done only once.
if __name__ == "__main__":

    # Get the curren path of the file
    dir, file = os.path.split(__file__)

    # Load the osimplecube.tif from res folder as a c4d BaseBitmap to be used as an icon.
    icon = bitmaps.BaseBitmap()
    icon.InitWith(os.path.join(dir, "res", "osimplecube.tif"))

    # Register the class SimpleCube as a Object Plugin to be used later in Cinema 4D.
    # param2 str即在菜单显示的文字，和新创建对象的名称
    plugins.RegisterObjectPlugin(id=PLUGIN_ID, str="SimpleCube",
                                g=SimpleCube,
                                description="simplecube", icon=icon,
                                info=c4d.OBJECT_GENERATOR)
