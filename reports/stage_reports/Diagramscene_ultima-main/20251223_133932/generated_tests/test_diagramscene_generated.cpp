// Generated test for DiagramScene (converted from testgen_report)
#include <gtest/gtest.h>
#include <QGraphicsScene>
#include <QMenu>
#include <QGraphicsView>
#include "../diagramscene.h"
#include "../diagramitem.h"
#include "../diagramtextitem.h"
#include "../arrow.h"
#include "../diagrampath.h"

using namespace std;

class DiagramSceneTest : public ::testing::Test {
protected:
    void SetUp() override {
        dummyMenu = new QMenu();
        scene = new DiagramScene(dummyMenu);
        view = new QGraphicsView(scene);
    }
    void TearDown() override {
        delete view;
        delete scene;
        delete dummyMenu;
    }
    QMenu *dummyMenu{nullptr};
    DiagramScene *scene{nullptr};
    QGraphicsView *view{nullptr};
};

TEST_F(DiagramSceneTest, ConstructorAndSceneRect) {
    EXPECT_TRUE(scene->items().isEmpty());
    EXPECT_EQ(scene->backgroundBrush().style(), Qt::SolidPattern);
    EXPECT_EQ(scene->sceneRect(), QRectF());
}

TEST_F(DiagramSceneTest, ModeAndItemTypeSetting) {
    scene->setMode(DiagramScene::InsertItem);
    EXPECT_EQ(scene->mode(), DiagramScene::InsertItem);
    scene->setMode(DiagramScene::InsertLine);
    EXPECT_EQ(scene->mode(), DiagramScene::InsertLine);
    scene->setMode(DiagramScene::InsertText);
    EXPECT_EQ(scene->mode(), DiagramScene::InsertText);
    scene->setMode(DiagramScene::MoveItem);
    EXPECT_EQ(scene->mode(), DiagramScene::MoveItem);

    scene->setItemType(DiagramItem::Step);
    EXPECT_EQ(scene->itemType(), DiagramItem::Step);
    scene->setItemType(DiagramItem::Conditional);
    EXPECT_EQ(scene->itemType(), DiagramItem::Conditional);
}

TEST_F(DiagramSceneTest, ColorAndFontAndInsertions) {
    QColor testColor(Qt::red);
    scene->setItemColor(testColor);
    scene->setLineColor(testColor);
    scene->setTextColor(testColor);
    EXPECT_EQ(scene->itemColor(), testColor);
    EXPECT_EQ(scene->lineColor(), testColor);
    EXPECT_EQ(scene->textColor(), testColor);

    QFont testFont("Arial", 12, QFont::Bold);
    scene->setFont(testFont);
    EXPECT_EQ(scene->font(), testFont);

    int initialCount = scene->items().count();
    DiagramItem *item = new DiagramItem(DiagramItem::Step, dummyMenu);
    scene->addItem(item);
    EXPECT_EQ(scene->items().count(), initialCount + 1);
    EXPECT_TRUE(scene->items().contains(item));

    DiagramTextItem *textItem = new DiagramTextItem();
    scene->addItem(textItem);
    EXPECT_TRUE(scene->items().contains(textItem));
}

TEST_F(DiagramSceneTest, SelectionAndDeletionAndSceneRect) {
    QRectF rect(0,0,1000,1000);
    scene->setSceneRect(rect);
    EXPECT_EQ(scene->sceneRect(), rect);

    DiagramItem *item = new DiagramItem(DiagramItem::Step, dummyMenu);
    scene->addItem(item);
    item->setSelected(true);
    EXPECT_TRUE(item->isSelected());
    EXPECT_FALSE(scene->selectedItems().isEmpty());

    scene->removeItem(item);
    delete item;
}

TEST_F(DiagramSceneTest, PathInsertionFlagSmoke) {
    // isInsertPath is a global/extern flag in upstream code; toggle it if available
    extern bool isInsertPath; // may be declared in project
    bool orig = isInsertPath;
    isInsertPath = true;
    EXPECT_TRUE(isInsertPath);
    isInsertPath = false;
    EXPECT_FALSE(isInsertPath);
    isInsertPath = orig;
}
