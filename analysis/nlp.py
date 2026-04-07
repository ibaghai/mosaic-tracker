"""
NLP skill extraction from job descriptions.
v1: regex/keyword matching — no ML dependencies.
"""

import re
from typing import List
from db.models import get_connection

# ── Skill Dictionary ──────────────────────────────────────────────────────────
# Keys are canonical skill names, values are regex patterns to match them.

_SKILLS = {
    # Languages
    'Python': r'\bPython\b',
    'Go': r'\bGo(?:lang)?\b',
    'Rust': r'\bRust\b',
    'TypeScript': r'\bTypeScript\b',
    'JavaScript': r'\bJavaScript\b',
    'Java': r'\bJava\b(?!Script)',
    'C++': r'\bC\+\+\b',
    'C#': r'\bC#\b',
    'Ruby': r'\bRuby\b',
    'Scala': r'\bScala\b',
    'Kotlin': r'\bKotlin\b',
    'Swift': r'\bSwift\b',
    'PHP': r'\bPHP\b',
    'SQL': r'\bSQL\b',
    'R': r'\bR\b(?=\s|,|\.|$)',
    'Elixir': r'\bElixir\b',
    'Haskell': r'\bHaskell\b',

    # Frontend
    'React': r'\bReact(?:\.js|JS)?\b',
    'Next.js': r'\bNext\.?js\b',
    'Vue': r'\bVue(?:\.?js)?\b',
    'Angular': r'\bAngular\b',
    'Svelte': r'\bSvelte\b',
    'Tailwind': r'\bTailwind\b',

    # Backend / Frameworks
    'Django': r'\bDjango\b',
    'FastAPI': r'\bFastAPI\b',
    'Flask': r'\bFlask\b',
    'Spring': r'\bSpring\b',
    'Rails': r'\bRails\b',
    'Express': r'\bExpress(?:\.js)?\b',
    'Node.js': r'\bNode\.?js\b',
    '.NET': r'\.NET\b',

    # Infrastructure
    'Kubernetes': r'\bKubernetes\b|\bk8s\b',
    'Docker': r'\bDocker\b',
    'Terraform': r'\bTerraform\b',
    'AWS': r'\bAWS\b',
    'GCP': r'\bGCP\b|\bGoogle Cloud\b',
    'Azure': r'\bAzure\b',
    'Linux': r'\bLinux\b',
    'Pulumi': r'\bPulumi\b',
    'Ansible': r'\bAnsible\b',
    'Helm': r'\bHelm\b',
    'ArgoCD': r'\bArgo\s?CD\b',
    'CI/CD': r'\bCI/?CD\b',
    'Jenkins': r'\bJenkins\b',
    'GitHub Actions': r'\bGitHub Actions\b',
    'Datadog': r'\bDatadog\b',
    'Grafana': r'\bGrafana\b',
    'Prometheus': r'\bPrometheus\b',

    # Data
    'Spark': r'\bSpark\b',
    'Kafka': r'\bKafka\b',
    'Airflow': r'\bAirflow\b',
    'dbt': r'\bdbt\b',
    'Snowflake': r'\bSnowflake\b',
    'BigQuery': r'\bBigQuery\b',
    'Redshift': r'\bRedshift\b',
    'Databricks': r'\bDatabricks\b',
    'Flink': r'\bFlink\b',

    # Databases
    'PostgreSQL': r'\bPostgres(?:QL)?\b',
    'MySQL': r'\bMySQL\b',
    'MongoDB': r'\bMongoDB\b|\bMongo\b',
    'Redis': r'\bRedis\b',
    'Elasticsearch': r'\bElasticsearch\b|\bElastic\b',
    'DynamoDB': r'\bDynamoDB\b',
    'Cassandra': r'\bCassandra\b',
    'ClickHouse': r'\bClickHouse\b',
    'Neo4j': r'\bNeo4j\b',

    # AI/ML
    'PyTorch': r'\bPyTorch\b',
    'TensorFlow': r'\bTensorFlow\b',
    'LLM': r'\bLLMs?\b|\blarge language model\b',
    'RAG': r'\bRAG\b',
    'Fine-tuning': r'\bfine[- ]?tun',
    'Transformers': r'\btransformer(?:s)?\b',
    'RLHF': r'\bRLHF\b',
    'Diffusion Models': r'\bdiffusion\s+model',
    'Computer Vision': r'\bcomputer vision\b|\bCV\b',
    'NLP': r'\bNLP\b|\bnatural language\b',
    'MLOps': r'\bMLOps\b',
    'Hugging Face': r'\bHugging\s?Face\b',
    'LangChain': r'\bLangChain\b',
    'Vector DB': r'\bvector\s+(?:db|database|store)\b|\bpinecone\b|\bweaviate\b|\bchroma\b',
    'CUDA': r'\bCUDA\b',
    'JAX': r'\bJAX\b',
    'scikit-learn': r'\bscikit[- ]?learn\b|\bsklearn\b',

    # Protocols / Practices
    'GraphQL': r'\bGraphQL\b',
    'REST': r'\bREST(?:ful)?\b',
    'gRPC': r'\bgRPC\b',
    'Microservices': r'\bmicroservices?\b',
    'Event-driven': r'\bevent[- ]driven\b',
    'OAuth': r'\bOAuth\b',

    # Mobile
    'iOS': r'\biOS\b',
    'Android': r'\bAndroid\b',
    'React Native': r'\bReact Native\b',
    'Flutter': r'\bFlutter\b',

    # Tools
    'Git': r'\bGit\b(?!Hub|Lab)',
    'Figma': r'\bFigma\b',
    'Jira': r'\bJira\b',
}

# Compile all patterns
_COMPILED = {name: re.compile(pattern, re.IGNORECASE) for name, pattern in _SKILLS.items()}


def extract_skills(text):
    # type: (str) -> List[str]
    """Extract skills from a job description. Returns list of canonical skill names."""
    if not text:
        return []
    found = []
    for name, pattern in _COMPILED.items():
        if pattern.search(text):
            found.append(name)
    return found


# ── Batch Processing ──────────────────────────────────────────────────────────

def extract_all_skills():
    """Extract skills from all job descriptions and populate job_skills table."""
    conn = get_connection()

    # Get jobs with descriptions that haven't been processed yet
    rows = conn.execute("""
        SELECT jp.id, jp.description
        FROM job_postings jp
        LEFT JOIN job_skills js ON js.job_id = jp.id
        WHERE jp.description IS NOT NULL
          AND js.job_id IS NULL
        GROUP BY jp.id
    """).fetchall()

    if not rows:
        conn.close()
        return 0

    total_skills = 0
    with conn:
        for r in rows:
            skills = extract_skills(r["description"])
            if skills:
                conn.executemany(
                    "INSERT OR IGNORE INTO job_skills (job_id, skill) VALUES (?, ?)",
                    [(r["id"], s) for s in skills]
                )
                total_skills += len(skills)

    conn.close()
    return total_skills


def get_skill_counts(active_only=True):
    # type: (bool) -> list
    """Get skill frequency counts."""
    conn = get_connection()
    where = "WHERE jp.is_active = 1" if active_only else ""
    rows = conn.execute("""
        SELECT js.skill, COUNT(*) as count
        FROM job_skills js
        JOIN job_postings jp ON jp.id = js.job_id
        {}
        GROUP BY js.skill
        ORDER BY count DESC
    """.format(where)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
