from app.database import get_supabase
sb = get_supabase()
users = sb.table("users").select("id,first_name,last_name").eq("last_name","Critic").execute()
print("Biased judge:", users.data)
if users.data:
    jid = users.data[0]["id"]
    evals = sb.table("evaluations").select("id,project_id,total_score,judge_id").eq("judge_id", jid).execute()
    print(f"Biased evals ({len(evals.data)}):")
    for e in evals.data:
        pid = e["project_id"]
        others = sb.table("evaluations").select("id,total_score,judge_id").eq("project_id", pid).execute()
        other_scores = [o["total_score"] for o in others.data if o["judge_id"] != jid]
        print(f"  Project {pid[:8]}... biased_score={e['total_score']}, other_scores={other_scores}")
