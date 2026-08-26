"""生成测试用长期 token（scope: all）"""
import ptoken
import psql

user_id = "sYLepkQgUlFdtpRkp3rYo"
participant_id = "7C64JubjmS5mpecsFkBTU"

# 验证用户/参与者存在
try:
    psql.get_user_from_id(id=user_id)
    print("USER_OK")
except Exception as e:
    print("USER_ERR", e)
try:
    psql.get_participant_from_id(id=participant_id)
    print("PARTICIPANT_OK")
except Exception as e:
    print("PARTICIPANT_ERR", e)

raw = ptoken.create_token(user_id=user_id, scopes=["all"], expiration_days=30, description="acceptance-test-20260826")
print("RAW_TOKEN=" + raw)
