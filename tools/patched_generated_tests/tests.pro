QT += testlib widgets
TEMPLATE = app
TARGET = tests
CONFIG += console
CONFIG -= app_bundle
CONFIG += c++17

SOURCES += \
    test_diagramitem.cpp \
    test_deletecommand.cpp \
    test_diagrampath.cpp \
    test_findreplacedialog.cpp

HEADERS += \
    test_diagramitem.h \
    test_deletecommand.h \
    test_diagrampath.h \
    test_findreplacedialog.h

# 调整 INCLUDEPATH 以便从 tests/generated 调用时能找到项目头文件
INCLUDEPATH += ../..

# 假设源文件位于项目根目录（Diagramscene_ultima-main），从 tests/generated 需要上两级
SOURCES += \
    ../../diagramitem.cpp \
    ../../deletecommand.cpp \
    ../../diagrampath.cpp \
    ../../findreplacedialog.cpp \
    ../../arrow.cpp \
    ../../diagramtextitem.cpp

HEADERS += \
    ../../diagramitem.h \
    ../../deletecommand.h \
    ../../diagrampath.h \
    ../../findreplacedialog.h \
    ../../arrow.h \
    ../../diagramtextitem.h \
    ../../diagramscene.h \
    ../../diagramitemgroup.h

DESTDIR = $$PWD
