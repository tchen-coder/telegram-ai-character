"""
模拟测试脚本 - 验证完整流程（不依赖真实 Telegram）
"""
import asyncio
import sys
sys.path.insert(0, '.')

from app.understanding import understanding_layer
from app.state_machine import state_machine
from app.decision import decision_engine
from app.prompt_agent import prompt_agent
from app.generation import generation_layer

async def simulate_conversation(user_id: str, user_name: str, messages: list[str]):
    """模拟一次完整对话流程"""
    
    print(f"\n{'='*60}")
    print(f"模拟用户: {user_name} ({user_id})")
    print(f"{'='*60}")
    
    # 初始化
    await state_machine.connect()
    await generation_layer.init()
    
    for i, user_text in enumerate(messages, 1):
        print(f"\n--- 第 {i} 轮对话 ---")
        print(f"👤 用户: {user_text}")
        
        # 1. 理解层
        emotion = await understanding_layer.analyze(user_text)
        print(f"📊 情绪识别: {emotion.user_emotion} (score={emotion.emotion_score:.2f})")
        
        # 2. 状态机
        state = await state_machine.get_state(user_id, user_name)
        print(f"📁 用户状态: level={state.relationship_level}, mood={state.character_mood:.2f}, count={state.interaction_count}")
        
        # 3. 决策机
        decision = decision_engine.decide(state, emotion)
        print(f"🎯 决策: reply_mood={decision.reply_mood}, flirt={decision.flirt_level}")
        
        # 4. Prompt 组装
        user_prompt = prompt_agent.build_prompt(state, emotion, decision)
        system_prompt = prompt_agent.SYSTEM_PROMPT
        
        # 5. 生成层 (调用 DeepSeek)
        print(f"🤖 正在生成回复...")
        try:
            response = await generation_layer.generate(system_prompt, user_prompt)
            print(f"💬 AI回复: {response}")
        except Exception as e:
            print(f"❌ 生成失败: {e}")
            continue
        
        # 6. 状态更新
        await state_machine.update_after_interaction(state, decision.mood_delta)
        print(f"📁 状态更新: mood={state.character_mood:.2f}, count={state.interaction_count}")
    
    await state_machine.close()
    print(f"\n{'='*60}")
    print("模拟测试完成!")
    print(f"{'='*60}")

async def main():
    # 模拟测试场景
    test_messages = [
        "你好呀~",
        "今天心情不太好",
        "谢谢你的关心，感觉好多了！",
    ]
    
    await simulate_conversation(
        user_id="test_user_001",
        user_name="测试用户",
        messages=test_messages
    )

if __name__ == "__main__":
    asyncio.run(main())
