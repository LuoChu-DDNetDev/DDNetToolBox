import os
import re
import shutil
from functools import partial

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFontMetrics, QPainter, QBrush, QPainterPath, QPixmap
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QStackedWidget, QLabel, QFileDialog, QHBoxLayout
from qfluentwidgets import CommandBar, Action, FluentIcon, InfoBar, InfoBarPosition, Pivot, TitleLabel, CardWidget, \
    ImageLabel, CaptionLabel, FlowLayout, SingleDirectionScrollArea, MessageBoxBase, SubtitleLabel, MessageBox, \
    SearchLineEdit, TogglePushButton, ToolTipFilter, ToolTipPosition, setFont, IndeterminateProgressRing, InfoBadge, \
    InfoBadgePosition
from win32comext.mapi.mapitags import PR_DELTAX

from app.config import cfg, base_path, config_path
from app.globals import GlobalsVal
from app.utils.draw_tee import draw_tee
from app.utils.network import JsonLoader, ImageLoader, HTMLoader

select_list = {
    "skins": {},
    "game": {},
    "emoticons": {},
    "cursor": {},
    "particles": {},
    "entities": {}
}
button_select = None


class ResourceCard(CardWidget):
    selected = False

    def __init__(self, data, card_type, parent=None):
        super().__init__(parent)
        global button_select

        self.card_type = card_type
        self.data = data
        self.file = data['name']
        self.setFixedSize(135, 120)

        if self.card_type == "skins":
            self.image_load = ImageLoader(f"https://teedata.net/api/skin/render/name/{data['name']}?emotion=default_eye")
            self.spinner = IndeterminateProgressRing()
        else:
            self.image_load = ImageLoader(f"https://teedata.net/databasev2{data['file_path']}")
            self.spinner = IndeterminateProgressRing()

        self.image_load.finished.connect(self.__on_image_load)
        self.image_load.start()

        self.label = CaptionLabel(self)
        self.label.setText(self.get_elided_text(self.label, self.data['name']))
        self.label.setToolTip(self.data['name'])
        self.label.setToolTipDuration(1000)
        self.label.installEventFilter(ToolTipFilter(self.label, showDelay=300, position=ToolTipPosition.BOTTOM))

        self.vBoxLayout = QVBoxLayout(self)
        self.vBoxLayout.addWidget(self.spinner, 0, Qt.AlignCenter)

        self.vBoxLayout.addWidget(self.label, 0, Qt.AlignCenter)

        self.clicked.connect(self.__on_clicked)

    def __on_image_load(self, pixmap: QPixmap):
        self.iconWidget = ImageLabel(pixmap)

        self.vBoxLayout.replaceWidget(self.spinner, self.iconWidget)
        self.spinner.deleteLater()

        if self.card_type == "skins":
            self.iconWidget.scaledToHeight(110)
        else:
            if self.card_type == "entities":
                self.iconWidget.scaledToHeight(100)
            else:
                self.iconWidget.scaledToHeight(60)

        self.iconWidget.stackUnder(self.label)

    def __on_clicked(self):
        self.set_selected(not self.selected)

    def set_selected(self, selected):
        self.selected = selected
        if self.selected:
            select_list[self.card_type][self.file] = self
        else:
            del select_list[self.card_type][self.file]
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.selected:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)

            rect = self.rect()
            path = QPainterPath()
            path.addRoundedRect(rect.x(), rect.y(), rect.width(), rect.height(), 5, 5)

            painter.setBrush(QBrush(cfg.get(cfg.themeColor)))
            painter.setPen(Qt.NoPen)
            painter.drawPath(path)

    def get_elided_text(self, label, text):
        # 省略文本
        metrics = QFontMetrics(label.font())
        available_width = label.width()

        elided_text = metrics.elidedText(text, Qt.ElideRight, available_width)
        return elided_text


class ResourceList(SingleDirectionScrollArea):
    refresh_resource = pyqtSignal()
    data_ready = pyqtSignal()
    batch_size = 1
    current_index = 0

    def __init__(self, list_type, parent=None):
        super().__init__(parent)
        self.list_type = list_type
        if self.list_type == "cursors" and not os.path.exists(f"{config_path}/app/ddnet_assets/cursor"):
            os.mkdir(f"{config_path}/app/ddnet_assets")
            os.mkdir(f"{config_path}/app/ddnet_assets/cursor")

        if self.list_type == "skins":
            self.file_path = f"{GlobalsVal.ddnet_folder}/{self.list_type}"
        elif self.list_type == "cursors":
            self.file_path = f"{config_path}/app/ddnet_assets/cursor"
        else:
            self.file_path = f"{GlobalsVal.ddnet_folder}/assets/{self.list_type}"

        self.containerWidget = QWidget()
        self.containerWidget.setStyleSheet("background: transparent;")
        self.fBoxLayout = FlowLayout(self.containerWidget)

        self.setContentsMargins(11, 11, 11, 11)
        self.setWidgetResizable(True)
        self.enableTransparentBackground()
        self.setWidget(self.containerWidget)

        self.refresh_resource.connect(self.__refresh)
        self.data_ready.connect(self.__data_ready)

    def load_next_batch(self):
        end_index = min(self.current_index + self.batch_size, len(self.teedata_list))
        for i in range(self.current_index, end_index):
            self.fBoxLayout.addWidget(ResourceCard(self.teedata_list[i], self.list_type))
        self.current_index = end_index

        if self.current_index < len(self.teedata_list):
            QTimer.singleShot(0, self.load_next_batch)

    def __refresh(self):
        for i in reversed(range(self.fBoxLayout.count())):
            widget = self.fBoxLayout.itemAt(i).widget()
            if widget:
                self.fBoxLayout.removeWidget(widget)
                widget.deleteLater()

        self.file_list = os.listdir(self.file_path)
        self.current_index = 0

        QTimer.singleShot(0, self.load_next_batch)

    def __data_ready(self, data=None):
        if data is None:
            self.teedata = JsonLoader(f"https://teedata.net/_next/data/{GlobalsVal.teedata_build_id}/{self.list_type}.json")
            self.teedata.finished.connect(self.__data_ready)
            self.teedata.start()
            return

        if self.list_type == 'skins':
            self.teedata_list = data['pageProps']['skins']['items']
        else:
            self.teedata_list = data['pageProps']['assets']['items']

        QTimer.singleShot(0, self.load_next_batch)
        # print(data)


class ResourceDownloadInterface(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ResourceDownloadInterface")

        if not GlobalsVal.ddnet_folder_status:
            self.label = SubtitleLabel("我们的程序无法自动找到DDNet配置目录\n请手动到设置中指定DDNet配置目录", self)
            self.hBoxLayout = QHBoxLayout(self)

            setFont(self.label, 24)
            self.label.setAlignment(Qt.AlignCenter)
            self.hBoxLayout.addWidget(self.label, 1, Qt.AlignCenter)
            return

        self.pivot = Pivot(self)
        self.stackedWidget = QStackedWidget(self)
        self.vBoxLayout = QVBoxLayout(self)

        self.hBoxLayout = QHBoxLayout()
        self.hBoxLayout.addWidget(TitleLabel('材质下载', self))
        self.hBoxLayout.addWidget(CaptionLabel("数据取自 teedata.net"), 0, Qt.AlignRight | Qt.AlignTop)

        self.search_edit = SearchLineEdit()
        self.search_edit.setPlaceholderText('搜点什么...')

        self.commandBar = CommandBar(self)
        self.commandBar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.addButton(FluentIcon.DOWNLOAD, '下载'),
        self.addButton(FluentIcon.SYNC, '刷新'),

        self.TeedataSkinsInterface = ResourceList('skins', self)
        self.TeedataGameSkinsInterface = ResourceList('gameskins', self)
        self.TeedataEmoticonsInterface = ResourceList('emoticons', self)
        self.TeedataCursorsInterface = ResourceList('cursors', self)  # gui_cursor.png
        self.TeedataParticlesInterface = ResourceList('particles', self)
        self.TeedataEntitiesInterface = ResourceList('entities', self)

        self.addSubInterface(self.TeedataSkinsInterface, 'TeedataSkinsInterface', '皮肤')
        self.addSubInterface(self.TeedataGameSkinsInterface, 'TeedataGameSkinsInterface', '贴图')
        self.addSubInterface(self.TeedataEmoticonsInterface, 'TeedataEmoticonsInterface', '表情')
        self.addSubInterface(self.TeedataCursorsInterface, 'TeedataCursorsInterface', '光标')
        self.addSubInterface(self.TeedataParticlesInterface, 'TeedataParticlesInterface', '粒子')
        self.addSubInterface(self.TeedataEntitiesInterface, 'TeedataEntitiesInterface', '实体层')

        self.headBoxLayout = QHBoxLayout()
        self.headBoxLayout.addWidget(self.pivot, 0, Qt.AlignLeft)
        self.headBoxLayout.addWidget(self.commandBar)

        self.vBoxLayout.addLayout(self.hBoxLayout)
        self.vBoxLayout.addWidget(self.search_edit)
        self.vBoxLayout.addLayout(self.headBoxLayout)
        self.vBoxLayout.addWidget(self.stackedWidget)

        self.stackedWidget.setCurrentWidget(self.TeedataSkinsInterface)
        self.pivot.setCurrentItem(self.TeedataSkinsInterface.objectName())
        self.pivot.currentItemChanged.connect(lambda k: self.stackedWidget.setCurrentWidget(self.findChild(QWidget, k)))

        self.teedata_build_id = HTMLoader("https://teedata.net/")
        self.teedata_build_id.finished.connect(self.__teedata_build_id_finished)

    def showEvent(self, event):
        super().showEvent(event)
        self.teedata_build_id.start()


    def __teedata_build_id_finished(self, data):
        match = re.search(r'"buildId":"(.*?)"', data)

        if match:
            GlobalsVal.teedata_build_id = match.group(1)
            self.__teedata_load_data()

    def __teedata_load_data(self):
        self.TeedataSkinsInterface.data_ready.emit()
        self.TeedataGameSkinsInterface.data_ready.emit()
        self.TeedataEmoticonsInterface.data_ready.emit()
        self.TeedataCursorsInterface.data_ready.emit()
        self.TeedataParticlesInterface.data_ready.emit()
        self.TeedataEntitiesInterface.data_ready.emit()

    def addSubInterface(self, widget: QLabel, objectName, text):
        widget.setObjectName(objectName)
        self.stackedWidget.addWidget(widget)
        self.pivot.addItem(routeKey=objectName, text=text)

    def addButton(self, icon, text):
        action = Action(icon, text, self)
        action.triggered.connect(partial(self.Button_clicked, text))
        self.commandBar.addAction(action)

    def Button_clicked(self, text):
        current_item = self.pivot.currentItem().text()

        if text == "下载":
            pass
        elif text == "刷新":
            InfoBar.success(
                title='成功',
                content="已重新加载本地资源",
                orient=Qt.Horizontal,
                isClosable=True,
                position=InfoBarPosition.BOTTOM_RIGHT,
                duration=2000,
                parent=GlobalsVal.main_window
            )

    def get_resource_pivot(self, text):
        if text == "皮肤":
            return self.TeedataSkinsInterface
        elif text == "贴图":
            return self.TeedataGameSkinsInterface
        elif text == "表情":
            return self.TeedataEmoticonsInterface
        elif text == "光标":
            return self.TeedataCursorsInterface
        elif text == "粒子":
            return self.TeedataParticlesInterface
        elif text == "实体层":
            return self.TeedataEntitiesInterface

    @staticmethod
    def get_resource_pivot_type(text):
        if text == "皮肤":
            text = "skins"
        elif text == "贴图":
            text = "game"
        elif text == "表情":
            text = "emoticons"
        elif text == "光标":
            text = "cursor"
        elif text == "粒子":
            text = "particles"
        elif text == "实体层":
            text = "entities"

        return text

    @staticmethod
    def get_resource_url(text):
        if text == "皮肤":
            text = "skins"
        elif text == "贴图":
            text = "game"
        elif text == "表情":
            text = "emoticons"
        elif text == "光标":
            text = "cursor"
        elif text == "粒子":
            text = "particles"
        elif text == "实体层":
            text = "entities"

        if text == "cursor" and not os.path.exists(f"{config_path}/app/ddnet_assets/cursor"):
            os.mkdir(f"{config_path}/app/ddnet_assets")
            os.mkdir(f"{config_path}/app/ddnet_assets/cursor")

        if text == "skins":
            file_path = f"{GlobalsVal.ddnet_folder}/{text}"
        elif text == "cursor":
            file_path = f"{config_path}/app/ddnet_assets/cursor"
        else:
            file_path = f"{GlobalsVal.ddnet_folder}/assets/{text}"

        return file_path
