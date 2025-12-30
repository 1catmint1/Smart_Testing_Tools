// Generated test for DiagramItemGroup (converted from testgen_report)
#include <gtest/gtest.h>
#include <QGraphicsScene>
#include <QGraphicsView>
#include "../diagramitemgroup.h"
#include "../diagramitem.h"
#include <QMenu>

using namespace std;

class DiagramItemGroupTest : public ::testing::Test {
protected:
    void SetUp() override {
        scene = new QGraphicsScene();
        view = new QGraphicsView(scene);
        dummyMenu = new QMenu();
        group = new DiagramItemGroup();
        scene->addItem(group);
        item1 = new DiagramItem(DiagramItem::Step, dummyMenu);
        item1->setPos(50, 50);
        item1->setFixedSize(QSizeF(100, 80));
        scene->addItem(item1);
        item2 = new DiagramItem(DiagramItem::Conditional, dummyMenu);
        item2->setPos(200, 100);
        item2->setFixedSize(QSizeF(120, 90));
        scene->addItem(item2);
    }
    void TearDown() override {
        delete view;
        delete scene;
        delete dummyMenu;
    }

    QGraphicsScene *scene{nullptr};
    QGraphicsView *view{nullptr};
    DiagramItemGroup *group{nullptr};
    DiagramItem *item1{nullptr};
    DiagramItem *item2{nullptr};
    QMenu *dummyMenu{nullptr};
};

TEST_F(DiagramItemGroupTest, ConstructorFlags) {
    DiagramItemGroup *newGroup = new DiagramItemGroup();
    EXPECT_NE(newGroup, nullptr);
    EXPECT_TRUE(newGroup->flags() & QGraphicsItem::ItemIsSelectable);
    EXPECT_TRUE(newGroup->flags() & QGraphicsItem::ItemIsMovable);
    EXPECT_TRUE(newGroup->acceptHoverEvents());
    delete newGroup;
}

TEST_F(DiagramItemGroupTest, AddItemsAndBoundingRect) {
    int initialChildCount = group->childItems().size();
    group->addItem(item1);
    EXPECT_EQ((int)group->childItems().size(), initialChildCount + 1);
    EXPECT_TRUE(group->childItems().contains(item1));
    group->addItem(item2);
    EXPECT_EQ((int)group->childItems().size(), initialChildCount + 2);
    EXPECT_TRUE(group->childItems().contains(item2));

    QRectF rect = group->boundingRect();
    EXPECT_GT(rect.width(), 0);
    EXPECT_GT(rect.height(), 0);
    EXPECT_EQ(rect.topLeft(), QPointF(0,0));
}

TEST_F(DiagramItemGroupTest, GetTopLeftAndSelectionPaint) {
    group->addItem(item1);
    group->addItem(item2);
    QPointF topLeft = group->getTopLeft();
    EXPECT_DOUBLE_EQ(topLeft.x(), 50.0);
    EXPECT_DOUBLE_EQ(topLeft.y(), 50.0);

    group->setSelected(true);
    EXPECT_TRUE(group->isSelected());
    group->update();
    EXPECT_TRUE(true);
}

TEST_F(DiagramItemGroupTest, HoverAndMouseEventsSmoke) {
    QGraphicsSceneHoverEvent hoverEvent(QEvent::GraphicsSceneHoverMove);
    hoverEvent.setPos(QPointF(10, 10));
    group->hoverMoveEvent(&hoverEvent);
    EXPECT_TRUE(true);

    QGraphicsSceneMouseEvent moveEvent(QEvent::GraphicsSceneMouseMove);
    moveEvent.setButton(Qt::LeftButton);
    moveEvent.setButtons(Qt::LeftButton);
    moveEvent.setPos(QPointF(15, 15));
    moveEvent.setLastPos(QPointF(5, 5));
    group->mouseMoveEvent(&moveEvent);
    EXPECT_TRUE(true);
}
