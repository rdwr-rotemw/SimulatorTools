"""Seed ALL polling structure templates into MongoDB."""

from backend.app.models.polling_structure import PollingStructure
from backend.app.utils.database import get_mongo_db


def seed_attack_data():
    """Seed attack_data structure."""
    mongo_db = get_mongo_db()
    polling_structures_collection = mongo_db["polling_structures"]

    structure = PollingStructure(
        structure_id="attack_data",
        name="Attack Data",
        description="DNS-Protection and Behavioral-DoS attack data",
        endpoint="/v1/attack-data",
        data_key="attack_data",
        polling_interval_seconds=60,
        data_structure={
            "attack_data": {
                "_type": "object",
                "_properties": {
                    "ErtFeed": {
                        "_type": "array",
                        "_item": {
                            "_type": "object",
                            "_properties": {
                                "policy_name": {"_type": "string"},
                                "attack_id": {"_type": "string"},
                                "time_from": {"_type": "timestamp", "_offset": 60},
                                "time_to": {"_type": "timestamp", "_offset": 0},
                                "data": {
                                    "_type": "array",
                                    "_item": {
                                        "_type": "object",
                                        "_properties": {
                                            "src-ip": {"_type": "string"},
                                            "src-port": {"_type": "number", "_min": 1, "_max": 65535},
                                            "dst-ip": {"_type": "string"},
                                            "dst-port": {"_type": "number", "_min": 1, "_max": 65535},
                                            "protocol": {"_type": "enum", "_options": ["tcp", "udp", "icmp", "sftp", "other"], "_value": "udp"},
                                            "tcp-flag": {"_type": "enum", "_options": ["SYN", "ACK", "FIN", "RST", "PSH", "URG", "SYN-ACK", "FIN-ACK"]},
                                            "packets": {"_type": "number", "_min": 1, "_max": 100000},
                                            "bytes": {"_type": "number", "_min": 64, "_max": 10000000}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "BDos": {
                        "_type": "array",
                        "_item": {
                            "_type": "object",
                            "_properties": {
                                "policy_name": {"_type": "string"},
                                "attack_id": {"_type": "string"},
                                "time_from": {"_type": "timestamp", "_offset": 60},
                                "time_to": {"_type": "timestamp", "_offset": 0},
                                "data": {
                                    "_type": "array",
                                    "_item": {
                                        "_type": "object",
                                        "_properties": {
                                            "src-ip": {"_type": "string"},
                                            "src-port": {"_type": "number", "_min": 1, "_max": 65535},
                                            "dst-ip": {"_type": "string"},
                                            "dst-port": {"_type": "number", "_min": 1, "_max": 65535},
                                            "protocol": {"_type": "enum", "_options": ["tcp", "udp", "icmp", "sftp", "other"], "_value": "udp"},
                                            "tcp-flag": {"_type": "enum", "_options": ["SYN", "ACK", "FIN", "RST", "PSH", "URG", "SYN-ACK", "FIN-ACK"]},
                                            "packets": {"_type": "number", "_min": 1, "_max": 100000},
                                            "bytes": {"_type": "number", "_min": 64, "_max": 10000000}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    existing = polling_structures_collection.find_one({"structure_id": "attack_data"})
    if existing:
        print("[OK]attack_data already exists")
        return

    polling_structures_collection.insert_one(structure.dict())
    print("✅ Seeded attack_data")


def seed_application_traffic_v1():
    """Seed application_traffic_v1 structure."""
    mongo_db = get_mongo_db()
    polling_structures_collection = mongo_db["polling_structures"]

    structure = PollingStructure(
        structure_id="application_traffic_v1",
        name="Application Traffic v1",
        description="Application traffic data (v1 format)",
        endpoint="/v1/traffic/application",
        data_key="application_traffic_v1",
        polling_interval_seconds=60,
        data_structure={
            "application_traffic_v1": {
                "_type": "array",
                "_item": {
                    "_type": "object",
                    "_properties": {
                        "policy_name": {"_type": "string"},
                        "time_from": {"_type": "timestamp", "_offset": 120},
                        "time_to": {"_type": "timestamp", "_offset": 60},
                        "data": {
                            "_type": "array",
                            "_item": {
                                "_type": "object",
                                "_properties": {
                                    "TLS-FP": {"_type": "string"},
                                    "packets": {"_type": "number", "_min": 1, "_max": 100000},
                                    "bytes": {"_type": "number", "_min": 64, "_max": 10000000}
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    existing = polling_structures_collection.find_one({"structure_id": "application_traffic_v1"})
    if existing:
        print("[OK]application_traffic_v1 already exists")
        return

    polling_structures_collection.insert_one(structure.dict())
    print("✅ Seeded application_traffic_v1")


def seed_application_traffic_v2():
    """Seed application_traffic_v2 structure."""
    mongo_db = get_mongo_db()
    polling_structures_collection = mongo_db["polling_structures"]

    structure = PollingStructure(
        structure_id="application_traffic_v2",
        name="Application Traffic v2",
        description="Application traffic data (v2 format)",
        endpoint="/v2/traffic/application",
        data_key="application_traffic_v2",
        polling_interval_seconds=60,
        data_structure={
            "application_traffic_v2": {
                "_type": "object",
                "_properties": {
                    "TLS-Fingerprint": {
                        "_type": "array",
                        "_item": {
                            "_type": "object",
                            "_properties": {
                                "policy_name": {"_type": "string"},
                                "time_from": {"_type": "timestamp", "_offset": 120},
                                "time_to": {"_type": "timestamp", "_offset": 60},
                                "data": {
                                    "_type": "array",
                                    "_item": {
                                        "_type": "object",
                                        "_properties": {
                                            "TLS-FP": {"_type": "string"},
                                            "packets": {"_type": "number", "_min": 1, "_max": 100000},
                                            "bytes": {"_type": "number", "_min": 64, "_max": 10000000}
                                        }
                                    }
                                }
                            }
                        }
                    },
                    "DNS-Protection": {
                        "_type": "array",
                        "_item": {
                            "_type": "object",
                            "_properties": {
                                "policy_name": {"_type": "string"},
                                "time_from": {"_type": "timestamp", "_offset": 120},
                                "time_to": {"_type": "timestamp", "_offset": 60},
                                "data": {
                                    "_type": "array",
                                    "_item": {
                                        "_type": "object",
                                        "_properties": {
                                            "fqdn": {"_type": "string"},
                                            "elements": {"_type": "number", "_min": 1, "_max": 100000}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    existing = polling_structures_collection.find_one({"structure_id": "application_traffic_v2"})
    if existing:
        print("[OK]application_traffic_v2 already exists")
        return

    polling_structures_collection.insert_one(structure.dict())
    print("✅ Seeded application_traffic_v2")


def seed_policy_traffic():
    """Seed policy_traffic structure."""
    mongo_db = get_mongo_db()
    polling_structures_collection = mongo_db["polling_structures"]

    structure = PollingStructure(
        structure_id="policy_traffic",
        name="Policy Traffic",
        description="Policy-based traffic statistics",
        endpoint="/v1/traffic/policy",
        data_key="policy_traffic",
        polling_interval_seconds=60,
        data_structure={
            "policy_traffic": {
                "_type": "array",
                "_item": {
                    "_type": "object",
                    "_properties": {
                        "policy_name": {"_type": "string"},
                        "direction": {"_type": "enum", "_options": ["in", "out"]},
                        "time_from": {"_type": "timestamp", "_offset": 120},
                        "time_to": {"_type": "timestamp", "_offset": 60},
                        "data": {
                            "_type": "array",
                            "_item": {
                                "_type": "object",
                                "_properties": {
                                    "dst-ip": {"_type": "string"},
                                    "bytes": {"_type": "number", "_min": 64, "_max": 10000000},
                                    "packets": {"_type": "number", "_min": 1, "_max": 100000}
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    existing = polling_structures_collection.find_one({"structure_id": "policy_traffic"})
    if existing:
        print("[OK]policy_traffic already exists")
        return

    polling_structures_collection.insert_one(structure.dict())
    print("✅ Seeded policy_traffic")


def seed_application_characteristics():
    """Seed application_characteristics structure."""
    mongo_db = get_mongo_db()
    polling_structures_collection = mongo_db["polling_structures"]

    structure = PollingStructure(
        structure_id="application_characteristics",
        name="Application Characteristics",
        description="Application characteristics and thresholds",
        endpoint="/v1/traffic/application/characteristics",
        data_key="application_characteristics",
        polling_interval_seconds=60,
        data_structure={
            "application_characteristics": {
                "_type": "object",
                "_properties": {
                    "Web-DDoS": {
                        "_type": "array",
                        "_item": {
                            "_type": "object",
                            "_properties": {
                                "policy_name": {"_type": "string"},
                                "time_from": {"_type": "timestamp", "_offset": 120},
                                "time_to": {"_type": "timestamp", "_offset": 60},
                                "thresholds": {
                                    "_type": "object",
                                    "_properties": {
                                        "policy-rate-alert-start": {"_type": "number", "_min": 0, "_max": 1000000},
                                        "policy-rate-alert-term": {"_type": "number", "_min": 0, "_max": 1000000},
                                        "policy-tlsfp-citizen-attack-start": {"_type": "number", "_min": 0, "_max": 1000000},
                                        "policy-tlsfp-citizen-attack-term": {"_type": "number", "_min": 0, "_max": 1000000},
                                        "policy-tlsfp-unknown-attack-start": {"_type": "number", "_min": 0, "_max": 1000000},
                                        "policy-tlsfp-unknown-attack-term": {"_type": "number", "_min": 0, "_max": 1000000}
                                    }
                                },
                                "data": {
                                    "_type": "array",
                                    "_item": {
                                        "_type": "object",
                                        "_properties": {
                                            "TLS-FP": {"_type": "string"},
                                            "citizen": {"_type": "boolean"},
                                            "portion": {"_type": "number", "_min": 0, "_max": 1},
                                            "average-hits": {"_type": "number", "_min": 0, "_max": 100000}
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    )

    existing = polling_structures_collection.find_one({"structure_id": "application_characteristics"})
    if existing:
        print("[OK]application_characteristics already exists")
        return

    polling_structures_collection.insert_one(structure.dict())
    print("✅ Seeded application_characteristics")


def seed_all():
    """Seed all structure templates."""
    print("Seeding polling structures...")
    seed_attack_data()
    seed_application_traffic_v1()
    seed_application_traffic_v2()
    seed_policy_traffic()
    seed_application_characteristics()
    print("All structures seeded!")


if __name__ == "__main__":
    seed_all()
