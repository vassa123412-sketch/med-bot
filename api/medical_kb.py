"""
Medical Knowledge Base from HealthKnowledgeGraph
157 diseases, 491 symptoms with probabilities
"""
import csv
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path("data/medical_knowledge/health_knowledge_graph.csv")


class MedicalKnowledgeBase:
    def __init__(self):
        self.diseases: Dict[str, Dict] = {}
        self.symptom_to_diseases: Dict[str, List[Dict]] = {}
        self._load()

    def _load(self):
        if not DATA_PATH.exists():
            logger.warning(f"Medical knowledge base not found at {DATA_PATH}")
            return

        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader)

            for row in reader:
                if len(row) < 2:
                    continue

                disease_name = row[0].strip()
                symptoms_str = row[1].strip()

                symptoms = []
                for part in symptoms_str.split(','):
                    part = part.strip()
                    if '(' in part and ')' in part:
                        name = part.split('(')[0].strip()
                        prob = float(part.split('(')[1].split(')')[0])
                        symptoms.append({"name": name, "probability": prob})

                self.diseases[disease_name] = {
                    "symptoms": symptoms,
                    "symptom_count": len(symptoms),
                }

                for s in symptoms:
                    symptom_name = s["name"].lower()
                    if symptom_name not in self.symptom_to_diseases:
                        self.symptom_to_diseases[symptom_name] = []
                    self.symptom_to_diseases[symptom_name].append({
                        "disease": disease_name,
                        "probability": s["probability"],
                    })

        logger.info(f"Loaded {len(self.diseases)} diseases, {len(self.symptom_to_diseases)} unique symptoms")

    def search_by_symptom(self, symptom: str, top_n: int = 10) -> List[Dict]:
        """Find diseases matching a symptom"""
        symptom_lower = symptom.lower()

        matches = []
        for key, diseases in self.symptom_to_diseases.items():
            if symptom_lower in key or key in symptom_lower:
                matches.extend(diseases)

        if not matches:
            for key, diseases in self.symptom_to_diseases.items():
                if any(word in key for word in symptom_lower.split()):
                    matches.extend(diseases)

        disease_scores = {}
        for m in matches:
            disease = m["disease"]
            if disease not in disease_scores:
                disease_scores[disease] = 0
            disease_scores[disease] += m["probability"]

        sorted_diseases = sorted(disease_scores.items(), key=lambda x: x[1], reverse=True)
        return [{"disease": d, "score": s} for d, s in sorted_diseases[:top_n]]

    def search_by_symptoms(self, symptoms: List[str], top_n: int = 10) -> List[Dict]:
        """Find diseases matching multiple symptoms"""
        all_matches = {}

        for symptom in symptoms:
            results = self.search_by_symptom(symptom, top_n=20)
            for r in results:
                disease = r["disease"]
                if disease not in all_matches:
                    all_matches[disease] = {"disease": disease, "score": 0, "matched_symptoms": []}
                all_matches[disease]["score"] += r["score"]
                all_matches[disease]["matched_symptoms"].append(symptom)

        sorted_results = sorted(all_matches.values(), key=lambda x: x["score"], reverse=True)
        return sorted_results[:top_n]

    def get_disease_info(self, disease_name: str) -> Optional[Dict]:
        """Get full info about a disease"""
        return self.diseases.get(disease_name)

    def get_top_symptoms(self, disease_name: str, top_n: int = 5) -> List[Dict]:
        """Get top symptoms for a disease"""
        disease = self.diseases.get(disease_name)
        if not disease:
            return []
        return sorted(disease["symptoms"], key=lambda x: x["probability"], reverse=True)[:top_n]

    def get_stats(self) -> Dict:
        return {
            "diseases": len(self.diseases),
            "unique_symptoms": len(self.symptom_to_diseases),
            "top_diseases": list(self.diseases.keys())[:10],
        }


medical_kb = MedicalKnowledgeBase()
