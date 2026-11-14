import db

def test_profile_and_goal_and_memory(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    db.save_profile("Amina", "University", "AI", "Python", "Step by step")
    assert db.get_profile()["name"] == "Amina"

    db.add_goal("Learn machine learning", "Study")
    assert db.list_goals()[0]["title"] == "Learn machine learning"

    db.add_memory("I prefer practical examples")
    memories = db.list_memories()
    assert memories[0]["content"] == "I prefer practical examples"

    db.delete_memory(memories[0]["id"])
    assert db.list_memories() == []
