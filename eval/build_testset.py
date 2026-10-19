"""Builds eval/testset.json from the seeds below.

Each answerable seed names the source PDF, the 1-based page and an evidence phrase
copied from that page. The relevant chunk IDs are then resolved from the existing
FAISS docstore (backend/faiss_index): a chunk is relevant if it comes from that file
and page and shares at least 6 consecutive words with the evidence phrase.

Reference answers paraphrase/quote the cited statute text. They were drafted by an
AI assistant from the indexed documents and have NOT been reviewed by a lawyer.

    python eval/build_testset.py
"""
import json
import pickle
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "backend" / "faiss_index" / "index.pkl"
OUT = Path(__file__).with_name("testset.json")

# (id, question, reference_answer, [(file, page, evidence), ...]); no evidence = unanswerable
SEEDS = [
    ("t01", "What is the punishment for murder under the Indian Penal Code?",
     "Under section 302 IPC, whoever commits murder shall be punished with death or imprisonment for life, and shall also be liable to fine.",
     [("IPC_pdf.pdf", 72, "Whoever commits murder shall be punished with death or imprisonment for life")]),
    ("t02", "What is the punishment for cheating and dishonestly inducing delivery of property?",
     "Under section 420 IPC, the offence is punishable with imprisonment of either description for a term which may extend to seven years, and the offender is also liable to fine.",
     [("IPC_pdf.pdf", 96, "Whoever cheats and thereby dishonestly induces the person deceived to deliver any property")]),
    ("t03", "What does Article 21 of the Constitution provide?",
     "Article 21 provides that no person shall be deprived of his life or personal liberty except according to procedure established by law.",
     [("ConstitutionOfIndia_pdf.pdf", 42, "No person shall be deprived of his life or personal liberty except according to procedure established by law")]),
    ("t04", "Which section of the Code of Criminal Procedure deals with anticipatory bail, and which courts can grant it?",
     "Section 438 CrPC: a person who has reason to believe he may be arrested on an accusation of a non-bailable offence may apply to the High Court or the Court of Session, which may direct that in the event of arrest he shall be released on bail.",
     [("CrPC_pdf.pdf", 182, "reason to believe that he may be arrested on an accusation of having committed a non bailable offence")]),
    ("t05", "What can happen to someone who logs in using another person's password without permission?",
     "Under section 66C of the IT Act (identity theft), whoever fraudulently or dishonestly makes use of the electronic signature, password or other unique identification feature of any other person shall be punished with imprisonment of either description up to three years and shall also be liable to fine.",
     [("ITAct_pdf.pdf", 24, "make use of the electronic signature, password or any other unique identification feature of any other person")]),
    ("t06", "Who is a child under the POCSO Act?",
     "Under section 2(1)(d) of the POCSO Act, 2012, \"child\" means any person below the age of eighteen years.",
     [("POCSO_pdf.pdf", 3, "child means any person below the age of eighteen years")]),
    ("t07", "Do you need a driving licence to drive a motor vehicle in a public place?",
     "Yes. Section 3 of the Motor Vehicles Act, 1988 provides that no person shall drive a motor vehicle in any public place unless he holds an effective driving licence.",
     [("MotorVehiclesAct_pdf.pdf", 11, "No person shall drive a motor vehicle in any public place unless he holds an effective driving licence")]),
    ("t08", "What is the penalty for driving without a driving licence?",
     "According to section 181 of the Motor Vehicles Act as it appears in the indexed text, driving in contravention of section 3 or 4 is punishable with imprisonment up to three months, or fine up to five hundred rupees, or both. (The indexed PDF may predate the 2019 amendment.)",
     [("MotorVehiclesAct_pdf.pdf", 88, "drives a motor vehicle in contravention of section 3 or section 4 shall be punishable with imprisonment for a term which may extend to three months")]),
    ("t09", "Can what a person said before dying about the cause of their death be used as evidence in court?",
     "Yes. Under section 32(1) of the Indian Evidence Act, a statement by a person who is dead as to the cause of his death or the circumstances of the transaction which resulted in his death is relevant where the cause of death comes into question, whether or not he expected death when making it.",
     [("IndianEvidenceAct_pdf.pdf", 22, "When the statement is made by a person as to the cause of his death")]),
    ("t10", "Can a confession made to a police officer be used against the accused?",
     "No. Section 25 of the Indian Evidence Act provides that no confession made to a police officer shall be proved as against a person accused of any offence.",
     [("IndianEvidenceAct_pdf.pdf", 21, "Confession to police officer not to be proved No confession made to a police officer")]),
    ("t11", "When can the police arrest a person without a warrant?",
     "Under section 41 CrPC, a police officer may arrest without an order from a Magistrate and without a warrant a person who commits a cognizable offence in his presence, or against whom a reasonable complaint, credible information or reasonable suspicion exists of a cognizable offence (subject to the conditions in the section), among other listed grounds.",
     [("CrPC_pdf.pdf", 40, "Any police officer may without an order from a Magistrate and without a warrant, arrest any person")]),
    ("t12", "How is an FIR recorded when someone reports a cognizable offence orally?",
     "Under section 154(1) CrPC, oral information about a cognizable offence given to the officer in charge of a police station shall be reduced to writing by him or under his direction, read over to the informant, signed by the informant, and its substance entered in a book kept by the officer.",
     [("CrPC_pdf.pdf", 78, "if given orally to an officer in charge of a police station, shall be reduced to writing by him or under his direction")]),
    ("t13", "Who can file a complaint under the Consumer Protection Act, 2019?",
     "Under section 35, a complaint about goods sold or services provided may be filed with a District Commission by the consumer concerned (including one alleging an unfair trade practice), by a recognised consumer association, and by others listed in the section.",
     [("ConsumerProtectionAct_pdf.pdf", 18, "complaint, in relation to any goods sold or delivered or agreed to be sold or delivered or any service provided")]),
    ("t14", "What is the punishment for theft?",
     "Under section 379 IPC, theft is punishable with imprisonment of either description for a term which may extend to three years, or with fine, or with both.",
     [("IPC_pdf.pdf", 89, "Whoever commits theft shall be punished with imprisonment of either description for a term which may extend to three years")]),
    ("t15", "What is the punishment for cruelty to a woman by her husband or his relatives?",
     "Under section 498A IPC, a husband or relative of the husband who subjects a woman to cruelty shall be punished with imprisonment up to three years and shall also be liable to fine.",
     [("IPC_pdf.pdf", 108, "subjects such woman to cruelty shall be punished with imprisonment for a term which may extend to three years")]),
    ("t16", "What is the minimum punishment for dowry death?",
     "Under section 304B(2) IPC, whoever commits dowry death shall be punished with imprisonment for not less than seven years, which may extend to imprisonment for life.",
     [("IPC_pdf.pdf", 72, "Whoever commits dowry death shall be punished with imprisonment for a term which shall not be less than seven years")]),
    ("t17", "Who can claim maintenance under the Code of Criminal Procedure?",
     "Under section 125 CrPC, where a person with sufficient means neglects or refuses to maintain his wife, minor child, adult child unable to maintain itself due to abnormality or injury (not a married daughter), or father or mother, unable to maintain themselves, a Magistrate of the first class may order a monthly maintenance allowance.",
     [("CrPC_pdf.pdf", 66, "If any person having sufficient means neglects or refuses to maintain")]),
    ("t18", "Which article of the Constitution abolishes untouchability?",
     "Article 17 abolishes \"Untouchability\" and forbids its practice in any form; enforcing any disability arising out of it is an offence punishable in accordance with law.",
     [("ConstitutionOfIndia_pdf.pdf", 40, "Untouchability is abolished and its practice in any form is forbidden")]),
    ("t19", "What must an arrested person be told about the reasons for their arrest, under the Constitution and under the CrPC?",
     "Article 22(1): an arrested person shall not be detained without being informed, as soon as may be, of the grounds of arrest, nor denied the right to consult a legal practitioner of his choice. Section 50(1) CrPC: a police officer arresting without warrant shall forthwith communicate full particulars of the offence or other grounds for the arrest.",
     [("ConstitutionOfIndia_pdf.pdf", 42, "No person who is arrested shall be detained in custody without being informed, as soon as may be, of the grounds for such arrest"),
      ("CrPC_pdf.pdf", 43, "shall forthwith communicate to him full particulars of the offence for which he is arrested or other grounds for such arrest")]),
    ("t20", "After how many years of continuous service does an employee become entitled to gratuity?",
     "According to the indexed study material on the Payment of Gratuity Act, gratuity is payable on termination after continuous service of not less than five years, except that five years are not required where termination is due to death or disablement.",
     [("LabourLaws_pdf.pdf", 145, "Gratuity shall be payable to an employee on the termination of his employment after he has rendered continuous service for not less than five years")]),
    # Not answerable from the indexed documents: the system should say so.
    ("t21", "What is the capital gains tax rate on selling listed shares?", None, []),
    ("t22", "What is the punishment for murder under the Bharatiya Nyaya Sanhita, and which section covers it?", None, []),
    ("t23", "What are the grounds for divorce under the Hindu Marriage Act?", None, []),
    ("t24", "Can my landlord evict me without notice in Delhi?", None, []),
    ("t25", "What did the Supreme Court hold in Vishaka v. State of Rajasthan?", None, []),
]


def squash(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def shingles(s: str, n: int = 6) -> list[str]:
    w = re.findall(r"[a-z0-9]+", s.lower())
    return ["".join(w[i:i + n]) for i in range(max(1, len(w) - n + 1))]


def main() -> None:
    with open(INDEX, "rb") as f:
        docstore, id_map = pickle.load(f)  # our own index file
    chunks = [(cid, docstore._dict[cid]) for cid in id_map.values()]
    items = []
    for tid, question, reference, evidence in SEEDS:
        relevant = []
        for file, page, phrase in evidence:
            sh = shingles(phrase)
            hits = [cid for cid, d in chunks
                    if Path(d.metadata.get("source", "").replace("\\", "/")).name == file
                    and d.metadata.get("page") == page - 1
                    and any(s in squash(d.page_content) for s in sh)]
            if not hits:
                raise SystemExit(f"{tid}: no chunk found for {file} p{page}: {phrase[:50]!r}")
            relevant.extend(hits)
        items.append({
            "id": tid,
            "question": question,
            "reference_answer": reference,
            "answerable": bool(evidence),
            "relevant_chunk_ids": relevant,
            "sources": [{"file": f, "page": p} for f, p, _ in evidence],
            "verified_by_human": False,
        })
    OUT.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {len(items)} items ({sum(i['answerable'] for i in items)} answerable) to {OUT}")


if __name__ == "__main__":
    main()
