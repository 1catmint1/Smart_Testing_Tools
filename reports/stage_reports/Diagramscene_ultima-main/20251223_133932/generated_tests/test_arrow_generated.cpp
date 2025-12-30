// Generated test for Arrow (converted from testgen_report)
#include <gtest/gtest.h>
#include "../arrow.h"
#include "../diagramitem.h"
#include <QGraphicsScene>
#include <QGraphicsView>

using namespace std;

class ArrowTest : public ::testing::Test {
protected:
    void SetUp() override {
        scene = new QGraphicsScene();
        startItem = new DiagramItem(DiagramItem::Step, nullptr);
        endItem = new DiagramItem(DiagramItem::Step, nullptr);
        scene->addItem(startItem);
        scene->addItem(endItem);
        startItem->setPos(0,0);
        endItem->setPos(100,100);
        arrow = new Arrow(startItem, endItem);
        scene->addItem(arrow);
    }
    void TearDown() override {
        delete scene;
    }
    QGraphicsScene *scene{nullptr};
    DiagramItem *startItem{nullptr};
    DiagramItem *endItem{nullptr};
    Arrow *arrow{nullptr};
};

TEST_F(ArrowTest, ConstructorAndFlags) {
    EXPECT_NE(arrow, nullptr);
    EXPECT_EQ(arrow->myStartItem, startItem);
    EXPECT_EQ(arrow->myEndItem, endItem);
    EXPECT_TRUE(arrow->flags() & QGraphicsItem::ItemIsSelectable);
}

TEST_F(ArrowTest, BoundingRectAndLine) {
    QRectF rect = arrow->boundingRect();
    EXPECT_TRUE(rect.isValid());
    EXPECT_FALSE(rect.isEmpty());
    QLineF line = arrow->line();
    EXPECT_TRUE(rect.contains(line.p1()));
    EXPECT_TRUE(rect.contains(line.p2()));
}

TEST_F(ArrowTest, UpdatePositionAndColor) {
    QLineF initialLine = arrow->line();
    endItem->setPos(200,200);
    arrow->updatePosition();
    QLineF newLine = arrow->line();
    EXPECT_NE(initialLine.p2(), newLine.p2());
    EXPECT_EQ(newLine.p1(), startItem->pos());
    EXPECT_EQ(newLine.p2(), endItem->pos());

    QColor newColor(Qt::red);
    arrow->setColor(newColor);
    EXPECT_EQ(arrow->myColor, newColor);
}

TEST_F(ArrowTest, Selection) {
    arrow->setSelected(true);
    EXPECT_TRUE(arrow->isSelected());
    arrow->setSelected(false);
    EXPECT_FALSE(arrow->isSelected());
}
