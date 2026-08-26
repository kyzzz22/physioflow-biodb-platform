// BioDB 测试数据清理（幂等，可重复执行）
// 用法: docker cp tools/cleanup_mongo_testdata.js biodb-main-mongo-1:/tmp/cleanup.js
//       docker exec biodb-main-mongo-1 mongosh -u root -p testtest --quiet --file /tmp/cleanup.js
// 保留: exp_emotion_verify（演示/验收数据）+ 其事件 evt_verify_001
const db2 = db.getSiblingDB('event_database');

const delExp = db2.experiments.deleteMany({
  experiment_id: { $in: ['f3ce3c17-1790-4de7-859d-9b9772468979'] },
});

const delEvt = db2.events.deleteMany({
  experiment_id: { $in: ['exp_emotion', 'exp_cognition', null] },
});

printjson({
  deleted_experiments: delExp.deletedCount,
  deleted_events: delEvt.deletedCount,
  remaining_experiments: db2.experiments.countDocuments(),
  remaining_events: db2.events.countDocuments(),
});
