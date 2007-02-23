############################################################################
##
## Copyright (C) 2006-2007 University of Utah. All rights reserved.
##
## This file is part of VisTrails.
##
## This file may be used under the terms of the GNU General Public
## License version 2.0 as published by the Free Software Foundation
## and appearing in the file LICENSE.GPL included in the packaging of
## this file.  Please review the following to ensure GNU General Public
## Licensing requirements will be met:
## http://www.opensource.org/licenses/gpl-license.php
##
## If you are unsure which license is appropriate for your use (for
## instance, you are interested in developing a commercial derivative
## of VisTrails), please contact us at vistrails@sci.utah.edu.
##
## This file is provided AS IS with NO WARRANTY OF ANY KIND, INCLUDING THE
## WARRANTY OF DESIGN, MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
##
############################################################################
""" This file describe the virtual cell layout widget used in
Parameter Exploration Tab """

from PyQt4 import QtCore, QtGui
from gui.common_widgets import QToolWindowInterface
from gui.theme import CurrentTheme
import string

################################################################################

class QVirtualCellWindow(QtGui.QFrame, QToolWindowInterface):
    """
    QVirtualCellWindow contains a caption, a virtual cell
    configuration
    
    """
    def __init__(self, parent=None):
        """ QVirtualCellWindow(parent: QWidget) -> QVirtualCellWindow
        Initialize the widget

        """
        QtGui.QFrame.__init__(self, parent)
        self.setFrameShape(QtGui.QFrame.StyledPanel)
        self.setWindowTitle('Spreadsheet Virtual Cell')
        vLayout = QtGui.QVBoxLayout(self)
        vLayout.setMargin(2)
        vLayout.setSpacing(0)
        self.setLayout(vLayout)
        
        label = QtGui.QLabel('Arrange the cell(s) below to construct'
                             ' a virtual cell')
        font = QtGui.QFont(label.font())
        font.setItalic(True)
        label.setFont(font)
        label.setWordWrap(True)        
        vLayout.addWidget(label)

        hLayout = QtGui.QVBoxLayout()
        hLayout.setMargin(0)
        hLayout.setSpacing(0)
        vLayout.addLayout(hLayout)
        self.config = QVirtualCellConfiguration()
        self.config.setSizePolicy(QtGui.QSizePolicy.Maximum,
                                  QtGui.QSizePolicy.Maximum)
        hLayout.addWidget(self.config)
        hPadWidget = QtGui.QWidget()
        hLayout.addWidget(hPadWidget)
        hPadWidget.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                 QtGui.QSizePolicy.Ignored)

        vPadWidget = QtGui.QWidget()
        vLayout.addWidget(vPadWidget)
        vPadWidget.setSizePolicy(QtGui.QSizePolicy.Expanding,
                                QtGui.QSizePolicy.Expanding)
        
class QVirtualCellConfiguration(QtGui.QWidget):
    """
    QVirtualCellConfiguration is a widget provide a virtual layout of
    the spreadsheet cell. Given a number of cells want to layout, it
    will let users interactively select where to put a cell in a table
    layout to construct a virtual cell out of that.
    
    """
    def __init__(self, parent=None):
        """ QVirtualCellConfiguration(parent: QWidget)
                                      -> QVirtualCellConfiguration
        Initialize the widget

        """
        QtGui.QWidget.__init__(self, parent)
        self.rowCount = 1
        self.colCount = 1
        gridLayout = QtGui.QGridLayout(self)
        gridLayout.setSpacing(0)
        self.setLayout(gridLayout)
        label = QVirtualCellLabel('')
        self.layout().addWidget(label, 0, 0, 1, 1, QtCore.Qt.AlignCenter)
        self.cells = [[label]]
        self.numCell = 1

    def clear(self):
        """ clear() -> None
        Remove and delete all widgets in self.gridLayout
        
        """
        while True:
            item = self.layout().takeAt(0)
            if item==None:
                break
            self.disconnect(item.widget(),
                            QtCore.SIGNAL('finishedDragAndDrop'),
                            self.compressCells)
            item.widget().deleteLater()
            del item
        self.cells = []
        self.numCell = 0

    def configVirtualCells(self, cells):
        """ configVirtualCells(cells: list of str) -> None        
        Given a list of cell types and ids, this will clear old
        configuration and start a fresh one.
        
        """
        self.clear()
        self.numCell = len(cells)
        row = []
        for i in range(self.numCell):
            label = QVirtualCellLabel(cells[i], i+1)
            row.append(label)
            self.layout().addWidget(label, 0, i, 1, 1, QtCore.Qt.AlignCenter)
            self.connect(label, QtCore.SIGNAL('finishedDragAndDrop'),
                         self.compressCells)
        self.cells.append(row)

        for r in range(self.numCell-1):
            row = []
            for c in range(self.numCell):
                label = QVirtualCellLabel()
                row.append(label)
                self.layout().addWidget(label, r+1, c, 1, 1,
                                        QtCore.Qt.AlignCenter)
                self.connect(label, QtCore.SIGNAL('finishedDragAndDrop'),
                             self.compressCells)
            self.cells.append(row)

    def compressCells(self):
        """ compressCells() -> None
        Eliminate all blank cells
        
        """
        # Check row by row first
        visibleRows = []
        for r in range(self.numCell):
            row = self.cells[r]
            hasRealCell = [True for label in row if label.type]!=[]
            if hasRealCell:                
                visibleRows.append(r)

        # Move rows up
        for i in range(len(visibleRows)):
            for c in range(self.numCell):
                label = self.cells[visibleRows[i]][c]
                if label.type==None:
                    label.type = ''
                self.cells[i][c].setCellData(label.type, label.id)

        # Now check column by column        
        visibleCols = []
        for c in range(self.numCell):
            hasRealCell = [True
                           for r in range(self.numCell)
                           if self.cells[r][c].type]!=[]
            if hasRealCell:
                visibleCols.append(c)
                    
        # Move columns left
        for i in range(len(visibleCols)):
            for r in range(self.numCell):
                label = self.cells[r][visibleCols[i]]
                if label.type==None:
                    label.type = ''
                self.cells[r][i].setCellData(label.type, label.id)

        # Clear redundant rows
        for i in range(self.numCell-len(visibleRows)):
            for label in self.cells[i+len(visibleRows)]:
                label.setCellData(None, -1)
                
        # Clear redundant columns
        for i in range(self.numCell-len(visibleCols)):
            for r in range(self.numCell):
                self.cells[r][i+len(visibleCols)].setCellData(None, -1)                

class QVirtualCellLabel(QtGui.QLabel):
    """
    QVirtualCellLabel is a label represent a cell inside a cell. It
    has rounded shape with a caption text
    
    """
    def __init__(self, label=None, id=-1, parent=None):
        """ QVirtualCellLabel(text: QString, id: int,
                              parent: QWidget)
                              -> QVirtualCellLabel
        Construct the label image

        """
        QtGui.QLabel.__init__(self, parent)
        self.setMargin(2)
        self.cellType = None
        self.setCellData(label, id)
        self.setAcceptDrops(True)
        self.setFrameStyle(QtGui.QFrame.Panel)
        self.palette().setColor(QtGui.QPalette.WindowText,
                                CurrentTheme.HOVER_SELECT_COLOR)

    def formatLabel(self, text):
        """ formatLabel(text: str) -> str
        Convert Camel Case to end-line separator
        
        """
        if text=='':
            return 'Empty'
        lines = []
        prev = 0
        lt = len(text)
        for i in range(lt):
            if (not (text[i] in string.lowercase)
                and (i==lt-1 or
                     text[i+1] in string.lowercase)):
                if i>0:
                    lines.append(text[prev:i])
                prev = i
        lines.append(text[prev:])
        return '\n'.join(lines)

    def setCellData(self, cellType, cellId):
        """ setCellData(cellType: str, cellId: int) -> None Create an
        image based on the cell type and id. Then assign it to the
        label. If cellType is None, the cell will be drawn with
        transparent background. If cellType is '', the cell will be
        drawn with the caption 'Empty'. Otherwise, the cell will be
        drawn with white background containing cellType as caption and
        a small rounded shape on the lower right painted with cellId
        
        """
        self.type = cellType
        self.id = cellId
        size = QtCore.QSize(*CurrentTheme.VIRTUAL_CELL_LABEL_SIZE)
        image = QtGui.QImage(size.width() + 12,
                             size.height()+ 12,
                             QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(0)

        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.ForceOutline)
        painter = QtGui.QPainter()
        painter.begin(image)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        if self.type==None:
#            painter.setPen(QtCore.Qt.lightGray)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtCore.Qt.NoBrush)
        else:
            if self.type=='':
                painter.setPen(QtCore.Qt.gray)
                painter.setBrush(QtCore.Qt.NoBrush)
            else:
                painter.setPen(QtCore.Qt.black)
                painter.setBrush(QtCore.Qt.lightGray)
        painter.drawRoundRect(QtCore.QRectF(0.5, 0.5, image.width()-1,
                                            image.height()-1), 25, 25)

        painter.setFont(font)
        if self.type!=None:
            painter.drawText(QtCore.QRect(QtCore.QPoint(6, 6), size),
                             QtCore.Qt.AlignCenter | QtCore.Qt.TextWrapAnywhere,
                                self.formatLabel(self.type))
            # Draw the lower right corner number if there is an id
            if self.id>=0 and self.type:
                QVirtualCellLabel.drawId(painter, image.rect(), self.id)

        painter.end()

        self.setPixmap(QtGui.QPixmap.fromImage(image))

    @staticmethod
    def drawId(painter, rect, id, center=False):
        """ drawId(painter: QPainter, rect: QRect, id: int, center:bool) -> None
        Draw the rounded id number on the right corner of rect in
        canvas painter. If center is true, the rounded is still drawn
        at the bottom right corner but with its center at the point
        
        """
        painter.setPen(CurrentTheme.VIRTUAL_CELL_LABEL_ID_BRUSH.color())
        painter.setBrush(CurrentTheme.VIRTUAL_CELL_LABEL_ID_BRUSH)
        font = QtGui.QFont()
        font.setStyleStrategy(QtGui.QFont.ForceOutline)
        font.setBold(True)
        painter.setFont(font)
        fm = QtGui.QFontMetrics(font)
        size = fm.size(QtCore.Qt.TextSingleLine, str(id))
        size = max(size.width(), size.height())
        if center:
            newRect = QtCore.QRect(rect.width()-size/2,
                                   rect.height()-size/2,
                                   size, size)
        else:
            newRect = QtCore.QRect(rect.width()-size,
                                   rect.height()-size,
                                   size, size)
        painter.drawEllipse(newRect)
        painter.setPen(CurrentTheme.VIRTUAL_CELL_LABEL_ID_PEN)
        painter.drawText(newRect, QtCore.Qt.AlignCenter, str(id))

    def mousePressEvent(self, event):
        """ mousePressEvent(event: QMouseEvent) -> None
        Start the drag and drop when the user click on the label
        
        """
        if self.type:
            mimeData = QtCore.QMimeData()
            mimeData.cellData = (self.type, self.id)

            drag = QtGui.QDrag(self)
            drag.setMimeData(mimeData)
            drag.setHotSpot(self.pixmap().rect().center())
            drag.setPixmap(self.pixmap())
            
            self.setCellData('', self.id)
            
            drag.start(QtCore.Qt.MoveAction)
            self.setCellData(*mimeData.cellData)
            self.emit(QtCore.SIGNAL('finishedDragAndDrop'))

    def dragEnterEvent(self, event):
        """ dragEnterEvent(event: QDragEnterEvent) -> None
        Set to accept drops from the other cell info
        
        """
        mimeData = event.mimeData()        
        if hasattr(mimeData, 'cellData'):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
            self.highlight()
        else:
            event.ignore()

    def dropEvent(self, event):        
        """ dropEvent(event: QDragMoveEvent) -> None
        Accept drop event to set the current cell
        
        """
        mimeData = event.mimeData()
        if hasattr(mimeData, 'cellData'):
            event.setDropAction(QtCore.Qt.MoveAction)
            event.accept()
            if self.id!=mimeData.cellData[1]:
                oldCellData = (self.type, self.id)
                self.setCellData(*mimeData.cellData)
                mimeData.cellData = oldCellData
        else:
            event.ignore()
        self.highlight(False)

    def dragLeaveEvent(self, event):
        """ dragLeaveEvent(event: QDragLeaveEvent) -> None
        Un highlight the current cell
        
        """
        self.highlight(False)

    def highlight(self, on=True):
        """ highlight(on: bool) -> None
        Highlight the cell as if being selected
        
        """
        if on:
            self.setFrameStyle(QtGui.QFrame.Panel | QtGui.QFrame.Plain)
        else:
            self.setFrameStyle(QtGui.QFrame.Panel)
                
################################################################################

if __name__=="__main__":        
    import sys
    import gui.theme
    app = QtGui.QApplication(sys.argv)
    gui.theme.initializeCurrentTheme()
    vc = QVirtualCellConfiguration()
    vc.configVirtualCells(['VTKCell', 'ImageViewerCell', 'RichTextCell'])
    vc.show()
    sys.exit(app.exec_())
