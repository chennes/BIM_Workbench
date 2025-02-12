# -*- coding: utf-8 -*-
#***************************************************************************
#*                                                                         *
#*   Copyright (c) 2018 Yorik van Havre <yorik@uncreated.net>              *
#*                                                                         *
#*   This program is free software; you can redistribute it and/or modify  *
#*   it under the terms of the GNU Lesser General Public License (LGPL)    *
#*   as published by the Free Software Foundation; either version 2 of     *
#*   the License, or (at your option) any later version.                   *
#*   for detail see the LICENCE text file.                                 *
#*                                                                         *
#*   This program is distributed in the hope that it will be useful,       *
#*   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
#*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
#*   GNU Library General Public License for more details.                  *
#*                                                                         *
#*   You should have received a copy of the GNU Library General Public     *
#*   License along with this program; if not, write to the Free Software   *
#*   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
#*   USA                                                                   *
#*                                                                         *
#***************************************************************************

from __future__ import print_function

"""The BIM library tool"""


import os
import FreeCAD
from BimTranslateUtils import *

FILTERS = ["*.fcstd","*.FCStd","*.FCSTD","*.stp","*.STP","*.step","*.STEP", "*.brp", "*.BRP", "*.brep", "*.BREP", "*.ifc", "*.IFC", "*.sat", "*.SAT"]
TEMPLIBPATH = os.path.join(FreeCAD.getUserAppDataDir(),"BIM","OfflineLibrary")
LIBRARYURL = "https://github.com/FreeCAD/FreeCAD-library/tree/master"
USE_API = True # True to use github API instead of web fetching... Way faster
REFRESH_INTERVAL = 3600 # Min seconds between allowing a new API calls (3600 = one hour)


# TODO as https://github.com/yorikvanhavre/BIM_Workbench/pull/77

# Tooltips on the "Link" and "Save" buttons
# I think the save button should be renamed a s"Save as..." (or maybe "Add to library...") so the user knows a new dialog will open
# Either "Insert >>" should become "Insert", or "Link" should become "Link >>"
# All the print() statements in your code should be replaced by FreeCAD.Console.PrintMessage() or FreeCAD.Console.PrintWarning() or FreeCAD.Console.PrintError() and the text should be placed in a translate() function and "\n" should be added to it. Example
#    FreeCAD.Console.PrintError(translate("BIM","Please save the document first")+"\n")
# I think the save button should go all the way to the bottom, below the search buttons, because it's a different kind of functionality than just "using" the library.
# It would be cool if the preview image would have a max width of the available column width, so if the task column is smaller than the image, it gets smaller to fit the space. I don't remember exactly how to do that, but it should be findable in QDesigner
# The open/closed state of the preview section should be remembered across sessions so when you use the tool again it is open if you left it open last time


class BIM_Library:


    def GetResources(self):

        return {'Pixmap'  : os.path.join(os.path.dirname(__file__),"icons","BIM_Library.svg"),
                'MenuText': QT_TRANSLATE_NOOP("BIM_Library", "Objects library"),
                'ToolTip' : QT_TRANSLATE_NOOP("BIM_Library", "Opens the objects library")}

    def Activated(self):

        import FreeCADGui

        # trying to locate the parts library
        libok = False
        self.librarypath = FreeCAD.ParamGet('User parameter:Plugins/parts_library').GetString('destination','')
        if self.librarypath:
            if os.path.exists(self.librarypath):
                libok = True
        else:
            # check if the library is at the standard addon location
            addondir = os.path.join(FreeCAD.getUserAppDataDir(),"Mod","parts_library")
            if os.path.exists(addondir):
                # save file paths with forward slashes even on windows
                FreeCAD.ParamGet('User parameter:Plugins/parts_library').SetString('destination',addondir.replace("\\","/"))
                libok = True
        FreeCADGui.Control.showDialog(BIM_Library_TaskPanel(offlinemode=libok))


class BIM_Library_TaskPanel:


    def __init__(self,offlinemode=False):

        from PySide import QtCore,QtGui
        import FreeCADGui

        self.mainDocName = FreeCAD.Gui.ActiveDocument.Document.Name
        self.previewDocName = "Viewer"

        self.linked = False

        self.librarypath = FreeCAD.ParamGet('User parameter:Plugins/parts_library').GetString('destination','')
        self.form = FreeCADGui.PySideUic.loadUi(os.path.join(os.path.dirname(__file__),"dialogLibrary.ui"))
        self.form.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","BIM_Library.svg")))

        # setting up a flat (no directories) file model for search
        self.filemodel = QtGui.QStandardItemModel()
        self.filemodel.setColumnCount(1)

        # setting up a directory model that shows only fcstd, step and brep
        self.dirmodel = LibraryModel()
        self.dirmodel.setRootPath(self.librarypath)
        self.dirmodel.setNameFilters(FILTERS)
        self.dirmodel.setNameFilterDisables(False)
        self.form.tree.setModel(self.dirmodel)
        self.form.tree.clicked[QtCore.QModelIndex].connect(self.clicked)
        self.form.buttonInsert.clicked.connect(self.insert)
        self.form.buttonLink.clicked.connect(self.linkfile)
        self.form.buttonSave.clicked.connect(self.addtolibrary)
        self.modelmode = 1 # 0 = File search, 1 = Dir mode

        # Don't show columns for size, file type, and last modified
        self.form.tree.setHeaderHidden(True)
        self.form.tree.hideColumn(1)
        self.form.tree.hideColumn(2)
        self.form.tree.hideColumn(3)
        self.form.tree.setRootIndex(self.dirmodel.index(self.librarypath))
        self.form.searchBox.textChanged.connect(self.onSearch)

        # setup UI
        self.form.buttonBimObject.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","bimobject.png")))
        self.form.buttonBimObject.clicked.connect(self.onBimObject)
        self.form.buttonNBSLibrary.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","nbslibrary.png")))
        self.form.buttonNBSLibrary.clicked.connect(self.onNBSLibrary)
        self.form.buttonBimTool.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","bimtool.png")))
        self.form.buttonBimTool.clicked.connect(self.onBimTool)
        self.form.button3DFindIt.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","3dfindit.svg")))
        self.form.button3DFindIt.clicked.connect(self.on3DFindIt)
        self.form.buttonGrabCad.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","grabcad.svg")))
        self.form.buttonGrabCad.clicked.connect(self.onGrabCad)
        self.form.checkOnline.toggled.connect(self.onCheckOnline)
        self.form.checkOnline.setChecked(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("LibraryOnline",not offlinemode))
        self.form.checkFCStdOnly.toggled.connect(self.onCheckFCStdOnly)
        self.form.checkFCStdOnly.setChecked(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("LibraryFCStdOnly",False))
        self.form.checkWebSearch.toggled.connect(self.onCheckWebSearch)
        self.form.checkWebSearch.setChecked(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("LibraryWebSearch",False))
        self.form.check3DPreview.toggled.connect(self.onCheck3DPreview)
        self.form.check3DPreview.setChecked(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("3DPreview",False))
        self.form.checkThumbnail.toggled.connect(self.onCheckThumbnail)
        self.form.checkThumbnail.setChecked(FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("SaveThumbnails",False))
        self.form.frameOptions.hide()
        self.form.buttonOptions.clicked.connect(self.onButtonOptions)
        self.form.buttonOptions.setText(translate("BIM","Options")+" ▼")
        self.form.framePreview.hide()
        self.form.buttonPreview.clicked.connect(self.onButtonPreview)
        self.form.buttonPreview.setText(translate("BIM","Preview")+" ▼")

        self.fcstdCB = QtGui.QCheckBox('FCStd')
        self.fcstdCB.setCheckState(QtCore.Qt.Checked)
        self.fcstdCB.setEnabled(False)
        self.fcstdCB.hide()
        self.stepCB = QtGui.QCheckBox('STEP')
        self.stepCB.setCheckState(QtCore.Qt.Checked)
        self.stepCB.hide()
        self.stlCB = QtGui.QCheckBox('STL')
        self.stlCB.setCheckState(QtCore.Qt.Checked)
        self.stlCB.hide()

    def clicked(self, index, previewDocName = "Viewer"):
        import Part, FreeCADGui, zipfile, tempfile, os
        self.previewOn = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("3DPreview",False)
        try:
            self.path = self.dirmodel.filePath(index)
        except:
            self.path = self.previousIndex
            print(self.path)
        self.isFile = os.path.isfile(self.path)
        # if the 3D preview checkbox is on ticked, show the preview
        if self.previewOn == True or self.linked == True:
            if self.isFile == True:
                # close a non linked preview document
                if self.linked == False:
                    try:
                        FreeCAD.closeDocument(self.previewDocName)
                    except:
                        pass
                # create different kinds of previews based on file type
                if self.path.lower().endswith(".stp") or self.path.lower().endswith(".step") or self.path.lower().endswith(".brp") or self.path.lower().endswith(".brep"):
                    self.previewDocName = "Viewer"
                    FreeCAD.newDocument(self.previewDocName)
                    FreeCAD.setActiveDocument(self.previewDocName)
                    Part.show(Part.read(self.path))
                    FreeCADGui.SendMsgToActiveView("ViewFit")
                elif self.path.lower().endswith(".fcstd"):
                    openedDoc = FreeCAD.openDocument(self.path)
                    FreeCADGui.SendMsgToActiveView("ViewFit")
                    self.previewDocName = FreeCAD.ActiveDocument.Name
                    thumbnailSave = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("SaveThumbnails",False)
                    if thumbnailSave == True:
                        FreeCAD.ActiveDocument.save()
        if self.linked == False:
            self.previousIndex = self.path

        # create a 2D image preview
        if self.path.lower().endswith(".fcstd"):
            zfile=zipfile.ZipFile(self.path)
            files=zfile.namelist()
            # check for meta-file if it's really a FreeCAD document
            if files[0] == "Document.xml":
                image="thumbnails/Thumbnail.png"
                if image in files:
                    image=zfile.read(image)
                    thumbfile = tempfile.mkstemp(suffix='.png')[1]
                    thumb = open(thumbfile,"wb")
                    thumb.write(image)
                    thumb.close()
                    im = QtGui.QPixmap(thumbfile)
                    self.form.framePreview.setPixmap(im)
                    return self.previewDocName, self.previousIndex, self.linked
        self.form.framePreview.clear()
        return self.previewDocName, self.previousIndex, self.linked

    def linkfile(self, index):
        import FreeCAD, FreeCADGui
        # check if the main document is open
        try:
            # check if the working document is saved
            if FreeCAD.getDocument(self.mainDocName).FileName == "":
                print("Please save the working file before linking.")
            else:
                self.previewOn = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("3DPreview",False)
                self.linked = True
                if self.previewOn != True:
                    BIM_Library_TaskPanel.clicked(self, index, previewDocName = "Viewer")
                self.librarypath = ""
                # save the file prior to linking
                BIM_Library_TaskPanel.addtolibrary(self)
                # link a document if it has been previously saved
                if self.fileDialog[0] != "":
                    FreeCADGui.Selection.clearSelection()
                    # link only root objects
                    for obj in FreeCAD.ActiveDocument.RootObjects:
                        FreeCADGui.Selection.addSelection(obj)
                    objects = FreeCADGui.Selection.getSelection()
                    # tries to create a link for each object in the selection
                    for obj in objects:
                        try:
                            link = FreeCAD.getDocument(self.mainDocName).addObject('App::Link','Link').setLink(obj)
                            #FreeCAD.getDocument(self.mainDocName).getObject('Link').Label=FreeCAD.ActiveDocument.ActiveObject.Label
                            FreeCAD.getDocument(self.mainDocName).getObject(link).Label=FreeCAD.ActiveDocument.ActiveObject.Label
                        except:
                            pass
                    FreeCAD.setActiveDocument(self.mainDocName)
                    self.librarypath = FreeCAD.ParamGet('User parameter:Plugins/parts_library').GetString('destination','')
                    self.linked = False
                    return self.linked
        except:
            print("It is not possible to link because the main document is closed.")

    def addtolibrary(self):
        import Part, Mesh, os
        self.fileDialog = QtGui.QFileDialog.getSaveFileName(None,u"Save As", self.librarypath)
        print(self.fileDialog[0])
        # check if file saving has been canceled and save .fcstd, .step and .stl copies
        if self.fileDialog[0] != "":
            # remove the file extension from the file path
            fileName = os.path.splitext(self.fileDialog[0])[0]
            FCfilename = fileName + ".fcstd"
            FreeCAD.ActiveDocument.saveAs(FCfilename)
            if self.stepCB.isChecked() or self.stlCB.isChecked():
                toexport = []
                objs = FreeCAD.ActiveDocument.Objects
                for obj in objs :
                    if obj.ViewObject.Visibility == True :
                        toexport.append(obj)
                if self.stepCB.isChecked() and self.linked == False:
                    STEPfilename = fileName + ".step"
                    Part.export(toexport,STEPfilename)
                if self.stlCB.isChecked() and self.linked == False:
                    STLfilename = fileName + ".stl"
                    Mesh.export(toexport,STLfilename)
        return self.fileDialog[0]

    def onSearch(self,text):

        if text:
            self.setSearchModel(text)
        else:
            self.setFileModel()

    def setSearchModel(self,text):

        import PartGui
        from PySide import QtGui
        self.form.tree.setModel(self.filemodel)
        self.filemodel.clear()
        if self.form.checkOnline.isChecked():
            res = self.getOfflineLib(structured = True)
        else:
            res = os.walk(self.librarypath)
        for dp,dn,fn in res:
            for f in fn:
                if text.lower() in f.lower():
                    if not os.path.isdir(os.path.join(dp,f)):
                        it = QtGui.QStandardItem(f)
                        it.setToolTip(os.path.join(dp,f))
                        self.filemodel.appendRow(it)
                        if f.endswith('.fcstd'):
                            it.setIcon(QtGui.QIcon(':icons/freecad-doc.png'))
                        elif f.endswith('.ifc'):
                            it.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","IFC.svg")))
                        else:
                            it.setIcon(QtGui.QIcon(':icons/Tree_Part.svg'))
        self.modelmode = 0

    def setFileModel(self):

        #self.form.tree.clear()
        self.form.tree.setModel(self.dirmodel)
        self.dirmodel.setRootPath(self.librarypath)
        self.dirmodel.setNameFilters(FILTERS)
        self.dirmodel.setNameFilterDisables(False)
        self.form.tree.setRootIndex(self.dirmodel.index(self.librarypath))
        self.modelmode = 1
        self.form.tree.setHeaderHidden(True)
        self.form.tree.hideColumn(1)
        self.form.tree.hideColumn(2)
        self.form.tree.hideColumn(3)

    def setOnlineModel(self):

        from PySide import QtGui

        def addItems(root,d,path):

            for k,v in d.items():
                it = QtGui.QStandardItem(k)
                root.appendRow(it)
                it.setToolTip(path+"/"+k)
                if isinstance(v,dict):
                    it.setIcon(QtGui.QIcon.fromTheme("folder",QtGui.QIcon(":/icons/Group.svg")))
                    addItems(it,v,path+"/"+k)
                    it.setToolTip("")
                elif k.lower().endswith('.fcstd'):
                    it.setIcon(QtGui.QIcon(':icons/freecad-doc.png'))
                elif k.lower().endswith('.ifc'):
                    it.setIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","IFC.svg")))
                else:
                    it.setIcon(QtGui.QIcon(':icons/Tree_Part.svg'))

        self.form.tree.setModel(self.filemodel)
        self.filemodel.clear()
        d = self.getOfflineLib()
        addItems(self.filemodel,d,":github")
        self.modelmode = 0

    def getOfflineLib(self,structured=False):

        def addDir(d,root):

            fn = []
            dn = []
            dp = []
            for k,v in d.items():
                if isinstance(v,dict):
                    fn2,dn2,dp2 = addDir(v,root+"/"+k)
                    fn.extend(fn2)
                    dn.extend(dn2)
                    dp.extend(dp2)
                else:
                    fn += k
                    dn += root
                    dp += root+"/"+k
            return dp,dn,fn

        templibfile = os.path.join(TEMPLIBPATH,"OfflineLibrary.py")
        if not os.path.exists(templibfile):
            FreeCAD.Console.PrintError(translate("BIM","No structure in cache. Please refresh.")+"\n")
            return {}
        import sys
        sys.path.append(TEMPLIBPATH)
        import OfflineLibrary
        d = OfflineLibrary.library
        if structured:
            return addDir(d,":github")
        else:
            return d


    def urlencode(self,text):

        import sys
        print(text,type(text))
        if sys.version_info.major < 3:
            import urllib
            return urllib.quote_plus(text)
        else:
            import urllib.parse
            return urllib.parse.quote_plus(text)

    def openUrl(self,url):

        from PySide import QtGui
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        s = p.GetBool("LibraryWebSearch",False)
        if s:
            import WebGui
            WebGui.openBrowser(url)
        else:
            QtGui.QDesktopServices.openUrl(url)

    def onBimObject(self):

        term = self.form.searchBox.text()
        if term:
            self.openUrl("https://www.bimobject.com/en/product?filetype=8&freetext="+self.urlencode(term))

    def onNBSLibrary(self):

        term = self.form.searchBox.text()
        if term:
            self.openUrl("https://www.nationalbimlibrary.com/en/search/?facet=Xo-P0w&searchTerm="+self.urlencode(term))

    def onBimTool(self):

        term = self.form.searchBox.text()
        if term:
            self.openUrl("https://www.bimtool.com/Catalog.aspx?criterio="+self.urlencode(term))

    def on3DFindIt(self):

        term = self.form.searchBox.text()
        if term:
            self.openUrl("https://www.3dfindit.com/textsearch?q="+self.urlencode(term))

    def onGrabCad(self):

        term = self.form.searchBox.text()
        if term:
            self.openUrl("https://grabcad.com/library?softwares=step-slash-iges&query="+self.urlencode(term))

    def needsFullSpace(self):

        return True

    def getStandardButtons(self):

        from PySide import QtGui
        return int(QtGui.QDialogButtonBox.Close)

    def reject(self):

        import FreeCADGui
        if hasattr(self,"box") and self.box:
            self.box.off()
        FreeCADGui.Control.closeDialog()
        FreeCAD.ActiveDocument.recompute()

    def insert(self, index=None):
        import FreeCADGui
        # check if the main document is open
        try:
            FreeCAD.setActiveDocument(self.mainDocName)
        except:
            print("It is not possible to insert because the main document is closed.")
            return
        FreeCAD.closeDocument(self.previewDocName)
        if not index:
            index = self.form.tree.selectedIndexes()
            if not index:
                return
            index = index[0]
        if self.modelmode == 1:
            path = self.dirmodel.filePath(index)
        else:
            path = self.filemodel.itemFromIndex(index).toolTip()
        if path.startswith(":github"):
            path = self.download(LIBRARYURL.replace("/tree","/raw") + "/" + path[7:])
        before = FreeCAD.ActiveDocument.Objects
        self.name = os.path.splitext(os.path.basename(path))[0]
        if path.lower().endswith(".stp") or path.lower().endswith(".step") or path.lower().endswith(".brp") or path.lower().endswith(".brep"):
            self.place(path)
        elif path.lower().endswith(".fcstd"):
            FreeCADGui.ActiveDocument.mergeProject(path)
            from DraftGui import todo
            todo.delay(self.reject,None)
        elif path.lower().endswith(".ifc"):
            import importIFC
            importIFC.ZOOMOUT = False
            importIFC.insert(path,FreeCAD.ActiveDocument.Name)
            from DraftGui import todo
            todo.delay(self.reject,None)
        elif path.lower().endswith(".sat") or path.lower().endswith(".sab"):
            try:
                # InventorLoader addon
                import importerIL
            except ImportError:
                try:
                    # CADExchanger addon
                    import CadExchangerIO
                except ImportError:
                    FreeCAD.Console.PrintError(translate("BIM","Error: Unable to import SAT files - CadExchanger addon must be installed"))
                else:
                    path = CadExchangerIO.insert(path,FreeCAD.ActiveDocument.Name,returnpath = True)
                    self.place(path)
            else:
                path = importerIL.insert(path,FreeCAD.ActiveDocument.Name)
        FreeCADGui.Selection.clearSelection()
        for o in FreeCAD.ActiveDocument.Objects:
            if not o in before:
                FreeCADGui.Selection.addSelection(o)
        FreeCADGui.SendMsgToActiveView("ViewSelection")

    def download(self,url):

        filepath = os.path.join(TEMPLIBPATH,url.split("/")[-1])
        url = url.replace(" ","%20")
        if not os.path.exists(filepath):
            from PySide import QtCore,QtGui
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            u = addonmanager_utilities.urlopen(url)
            if not u:
                FreeCAD.Console.PrintError(translate("BIM", "Error: Unable to download")+ " "+url+"\n")
            b = u.read()
            f = open(filepath,"wb")
            f.write(b)
            f.close()
            QtGui.QApplication.restoreOverrideCursor()
        return filepath

    def place(self,path):

        import FreeCADGui
        import Part
        self.shape = Part.read(path)
        if hasattr(FreeCADGui,"Snapper"):
            try:
                import DraftTrackers
            except Exception:
                import draftguitools.gui_trackers as DraftTrackers
            self.box = DraftTrackers.ghostTracker(self.shape,dotted=True,scolor=(0.0,0.0,1.0),swidth=1.0)
            self.delta = self.shape.BoundBox.Center
            self.box.move(self.delta)
            self.box.on()
            if hasattr(FreeCAD,"DraftWorkingPlane"):
                FreeCAD.DraftWorkingPlane.setup()
            self.origin = self.makeOriginWidget()
            FreeCADGui.Snapper.getPoint(movecallback=self.mouseMove,callback=self.mouseClick,extradlg=self.origin)
        else:
            Part.show(self.shape)

    def makeOriginWidget(self):

        from PySide import QtGui
        w = QtGui.QWidget()
        w.setWindowTitle(translate("BIM","Insertion point"))
        w.setWindowIcon(QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","BIM_Library.svg")))
        l = QtGui.QVBoxLayout()
        w.setLayout(l)
        c = QtGui.QComboBox()
        c.ObjectName = "comboOrigin"
        w.comboOrigin = c
        c.addItems([translate("BIM","Origin"),translate("BIM","Top left"),translate("BIM","Top center"),
                    translate("BIM","Top right"),translate("BIM","Middle left"),translate("BIM","Middle center"),
                    translate("BIM","Middle right"),translate("BIM","Bottom left"),translate("BIM","Bottom center"),
                    translate("BIM","Bottom right")])
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetInt("LibraryDefaultInsert",0)
        c.setCurrentIndex(p)
        c.currentIndexChanged.connect(self.storeInsert)
        l.addWidget(c)
        return w

    def storeInsert(self,index):

        FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").SetInt("LibraryDefaultInsert",index)

    def mouseMove(self,point,info):

        self.box.move(point.add(self.getDelta()))

    def mouseClick(self,point,info):

        if point:
            import Arch
            self.box.off()
            self.shape.translate(point.add(self.getDelta()))
            obj = Arch.makeEquipment()
            obj.Shape = self.shape
            obj.Label = self.name
        self.reject()

    def getDelta(self):

        d = FreeCAD.Vector(-self.shape.BoundBox.Center.x,-self.shape.BoundBox.Center.y,0)
        idx = self.origin.comboOrigin.currentIndex()
        if idx <= 0:
            return FreeCAD.Vector()
        elif idx == 1:
            return d.add(FreeCAD.Vector(self.shape.BoundBox.XLength/2,-self.shape.BoundBox.YLength/2,0))
        elif idx == 2:
            return d.add(FreeCAD.Vector(0,-self.shape.BoundBox.YLength/2,0))
        elif idx == 3:
            return d.add(FreeCAD.Vector(-self.shape.BoundBox.XLength/2,-self.shape.BoundBox.YLength/2,0))
        elif idx == 4:
            return d.add(FreeCAD.Vector(self.shape.BoundBox.XLength/2,0,0))
        elif idx == 5:
            return d
        elif idx == 6:
            return d.add(FreeCAD.Vector(-self.shape.BoundBox.XLength/2,0,0))
        elif idx == 7:
            return d.add(FreeCAD.Vector(self.shape.BoundBox.XLength/2,self.shape.BoundBox.YLength/2,0))
        elif idx == 8:
            return d.add(FreeCAD.Vector(0,self.shape.BoundBox.YLength/2,0))
        elif idx == 9:
            return d.add(FreeCAD.Vector(-self.shape.BoundBox.XLength/2,self.shape.BoundBox.YLength/2,0))

    def getOnlineContentsWEB(self,url):

        """Returns a dirs,files pair representing files found from a github url. OBSOLETE"""

        # obsolete code - now using getOnlineContentsAPI

        import addonmanager_utilities
        result = {}
        u = addonmanager_utilities.urlopen(url)
        if u:
            p = u.read()
            if sys.version_info.major >= 3:
                p = str(p)
            dirs = re.findall("<.*?octicon-file-directory.*?href.*?>(.*?)</a>",p)
            files = re.findall("<.*?octicon-file\".*?href.*?>(.*?)</a>",p)
            nfiles = []
            for f in files:
                for ft in FILTERS:
                    if f.endswith(ft[1:]):
                        nfiles.append(f)
                        break
            files = nfiles
            for d in dirs:
                # <spans>
                if "</span" in d:
                    d1 = re.findall("<span.*?>(.*?)<",d)
                    d2 = re.findall("</span>(.*?)$",d)
                    if d1 and d2:
                        d = d1[0] + "/" + d2[0]
                r = self.getOnlineContentsWEB(url+"/"+d.replace(" ","%20"))
                result[d] = r
            for f in files:
                result[f] = f
        else:
            FreeCAD.Console.PrintError(translate("BIM","Cannot open URL")+":"+url+"\n")
        return result

    def getOnlineContentsAPI(self,url):

        """same as getOnlineContents but uses github API (faster)"""

        result = {}
        import requests
        import json
        count = 0
        r = requests.get('https://api.github.com/repos/FreeCAD/FreeCAD-library/git/trees/master?recursive=1')
        if r.ok:
            j = json.loads(r.content)
            if j['truncated']:
                print("WARNING: The fetched content exceeds maximum Github allowance and is truncated")
            t = j['tree']
            for f in t:
                path = f['path'].split("/")
                if f['type'] == 'tree':
                    name = None
                else:
                    name = path[-1]
                    path = path[:-1]
                host = result
                for fp in path:
                    if fp in host:
                        host = host[fp]
                    else:
                        host[fp] = {}
                        host = host[fp]
                if name:
                    for ft in FILTERS:
                        if name.endswith(ft[1:]):
                            break
                    else:
                        continue
                    host[name] = name
                    count += 1
        else:
            FreeCAD.Console.PrintError(translate("BIM","Could not fetch library contents")+"\n")
        #print("result:",result)
        if not result:
            FreeCAD.Console.PrintError(translate("BIM","No results fetched from online library")+"\n")
        else:
            FreeCAD.Console.PrintLog("BIM Library: Reloaded "+str(count)+" files")
        return result


    def onCheckOnline(self,state):

        """if the Online checkbox is clicked"""

        import datetime
        # save state
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        p.SetBool("LibraryOnline",state)
        if state:
            # online
            if USE_API:
                timestamp = datetime.datetime.now()
                stored = p.GetUnsigned("LibraryTimeStamp",0)
                if stored:
                    stored = datetime.datetime.fromordinal(stored)
                    if(timestamp - stored).total_seconds() > REFRESH_INTERVAL:
                        p.SetUnsigned("LibraryTimeStamp",timestamp.toordinal())
                        self.onRefresh()
                    else:
                        FreeCAD.Console.PrintLog("BIM Library: Using cached library\n")
                else:
                    FreeCAD.Console.PrintLog("BIM Library: Using cached library\n")
            self.setOnlineModel()
        else:
            # offline
            self.setFileModel()

    def onRefresh(self):

        """refreshes the tree"""

        def writeOfflineLib():

            if USE_API:
                rootfiles = self.getOnlineContentsAPI(LIBRARYURL)
            else:
                rootfiles = self.getOnlineContentsWEB(LIBRARYURL)
            if rootfiles:
                templibfile = os.path.join(TEMPLIBPATH,"OfflineLibrary.py")
                tf = open(templibfile,"w")
                tf.write("library="+str(rootfiles))
                tf.close()

        from PySide import QtCore,QtGui
        reply = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("LibraryWarning",False)
        if not reply:
            reply = QtGui.QMessageBox.information(None,"",translate("BIM","Warning, this can take several minutes!"))
        if reply:
            FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").SetBool("LibraryWarning",True)
            self.form.setEnabled(False)
            QtGui.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
            self.form.repaint()
            QtGui.QApplication.processEvents()
            QtCore.QTimer.singleShot(1,writeOfflineLib)
            self.form.setEnabled(True)
            QtGui.QApplication.restoreOverrideCursor()
        self.setOnlineModel()

    def onCheckFCStdOnly(self,state):

        """if the FCStd only checkbox is clicked"""

        # save state
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        p.SetBool("LibraryFCStdOnly",state)

    def onCheckWebSearch(self,state):

        """if the web search checkbox is clicked"""

        # save state
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        p.SetBool("LibraryWebSearch",state)

    def onCheck3DPreview(self,state):

        """if the 3D preview checkbox is clicked"""

        import FreeCADGui
        # save state
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        p.SetBool("3DPreview",state)
        self.previewOn = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM").GetBool("3DPreview",False)
        try:
            FreeCAD.closeDocument(self.previewDocName)
        except:
            pass
        if self.previewOn == True:
            self.previewDocName = "Viewer"
            self.doc = FreeCAD.newDocument(self.previewDocName)
            FreeCADGui.ActiveDocument.ActiveView.viewIsometric()
            return self.previewDocName

    def onCheckThumbnail(self,state):

        """if the thumbnail checkbox is clicked"""

        # save state
        p = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/Mod/BIM")
        p.SetBool("SaveThumbnails",state)

    def onButtonOptions(self):

        """hides/shows the options"""

        if self.form.frameOptions.isVisible():
            self.form.frameOptions.hide()
            self.form.buttonOptions.setText(translate("BIM","Options")+" ▼")
        else:
            self.form.frameOptions.show()
            self.form.buttonOptions.setText(translate("BIM","Options")+" ▲")

    def onButtonPreview(self):

        """hides/shows the preview"""

        if self.form.framePreview.isVisible():
            self.form.framePreview.hide()
            self.form.buttonPreview.setText(translate("BIM","Preview")+" ▼")
        else:
            self.form.framePreview.show()
            self.form.buttonPreview.setText(translate("BIM","Preview")+" ▲")


if FreeCAD.GuiUp:

    from PySide import QtCore,QtGui

    class LibraryModel(QtGui.QFileSystemModel):

        "a custom QFileSystemModel that displays freecad file icons"

        def __init__(self):

            QtGui.QFileSystemModel.__init__(self)

        def data(self, index, role):

            if index.column() == 0 and role == QtCore.Qt.DecorationRole:
                if index.data().lower().endswith('.fcstd'):
                    return QtGui.QIcon(':icons/freecad-doc.png')
                elif index.data().lower().endswith('.ifc'):
                    return QtGui.QIcon(os.path.join(os.path.dirname(__file__),"icons","IFC.svg"))
                elif index.data().lower() == "private":
                    return QtGui.QIcon.fromTheme("folder-lock")
            return super(LibraryModel, self).data(index, role)
