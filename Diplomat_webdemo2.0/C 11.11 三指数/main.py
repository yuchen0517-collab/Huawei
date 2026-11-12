from engine import NegotiationState, validate_action, apply_effects

if __name__ == "__main__":
    print("引擎加载成功")
    test_state = NegotiationState(session_id="test_001")
    print("NegotiationState 实例创建成功\n", test_state)

    # 构造一个谈判动作（提案 offer）
    test_action = {
        "party": "A",
        "type": "offer",
        "content": {"terms": {"trade_concession": 10}}
    }

    # 1. 校验动作是否合法，先只拿到返回值打印
    ret = validate_action(test_state, test_action)
    print("validate_action 返回值：", ret)