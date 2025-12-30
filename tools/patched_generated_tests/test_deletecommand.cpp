#include <QtTest>
#include <QGraphicsScene>
#include <QGraphicsRectItem>
#include "../../deletecommand.h"

class TestDeleteCommand : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();
    void testConstructor();
    void testUndoRedo();

private:
    QGraphicsScene *scene;
    QGraphicsRectItem *rectItem;
    DeleteCommand *command;
};

void TestDeleteCommand::initTestCase()
{
    scene = new QGraphicsScene();
    rectItem = new QGraphicsRectItem(0, 0, 100, 100);
    scene->addItem(rectItem);
    command = new DeleteCommand(rectItem, scene);
}

void TestDeleteCommand::cleanupTestCase()
{
    delete command;
    delete scene;
}

void TestDeleteCommand::testConstructor()
{
    QVERIFY(command != nullptr);
    // 不直接访问私有成员，改为通过行为验证
    QVERIFY(scene->items().contains(rectItem));
}

void TestDeleteCommand::testUndoRedo()
{
    // 初始状态：项目在场景中
    QVERIFY(scene->items().contains(rectItem));
    
    // 执行 redo (删除)
    command->redo();
    QVERIFY(!scene->items().contains(rectItem));
    
    // 执行 undo (恢复)
    command->undo();
    QVERIFY(scene->items().contains(rectItem));
    
    // 再次 redo
    command->redo();
    QVERIFY(!scene->items().contains(rectItem));
}

QTEST_MAIN(TestDeleteCommand)
#include "test_deletecommand.moc"
