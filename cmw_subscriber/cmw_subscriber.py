import datetime
import logging
import redis
import pytz
import pyjapc

TZ = pytz.timezone('Europe/Zurich')
BUFFERLEN = 7200
CRIO_GUN = "TwinEBIS_cRIO_Gun"
CRIO_HV = "TwinEBIS_cRIO_HV"

PSU_HV = [
    {"name":"HV_GunBias", "id":0},
    {"name":"HV_AnodeDt", "id":1},
    {"name":"HV_InnerBarrier", "id":2},
    {"name":"HV_Extractor", "id":3},
]

PSU_GUN = [
    {"name":"GUN_CathodeHeating", "id":0},
    {"name":"GUN_Wehnelt", "id":1},
    {"name":"GUN_Anode", "id":2},
    {"name":"GUN_Suppressor", "id":3},
    {"name":"GUN_Collector", "id":4},
    {"name":"GUN_Extractor", "id":5},
]

GAUGES_HV = [
    {"name":"EBIS_Gun_Penning", "channel":"Gun Penning"},
    {"name":"EBIS_Collector_Penning", "channel":"EBIS Collecter Penning"}
]


def start_logger():
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger_stream_handler = logging.StreamHandler()
    # logfmt = "[%(asctime)s][%(name)s][%(levelname)s]:%(message)s"
    logfmt = "[%(asctime)s][%(levelname)s]:%(message)s"
    logger_stream_handler.formatter = logging.Formatter(logfmt)
    logger.addHandler(logger_stream_handler)
    return logger

def main():
    logger = start_logger()

    # rcl = redis.Redis(host='redis')
    rcl = redis.Redis()
    logger.info("Redis connection opened.")

    japc = pyjapc.PyJapc(incaAcceleratorName=None)
    logger.info("PyJAPC initialised.")


    def broker_psus(name, values):
        psus = PSU_GUN if CRIO_GUN in name else PSU_HV
        timestamp = datetime.datetime.now(TZ).isoformat()
        with rcl.pipeline(transaction=True) as pipe:
            for psu in psus:
                name = psu["name"]
                val = values[psu["id"]]
                pipe.lpush(f"psu:{name}:iread:val", val)
                pipe.lpush(f"psu:{name}:iread:t", timestamp)
                pipe.ltrim(f"psu:{name}:iread:val", 0, BUFFERLEN-1)
                pipe.ltrim(f"psu:{name}:iread:t", 0, BUFFERLEN-1)
                logger.info(f"Queued push to psu:{name}:*")
            pipe.execute()
            logger.info(f"Push to psu:{name}:* executed.")

    def broker_gauges(name, values):
        if CRIO_HV in name:
            gauges = GAUGES_HV
        else:
            raise NotImplementedError
        timestamp = datetime.datetime.now(TZ).isoformat()
        with rcl.pipeline(transaction=True) as pipe:
            for gauge in gauges:
                name = gauge["name"]
                val = values[gauge["channel"]]
                pipe.lpush(f"gauge:{name}:val", val)
                pipe.lpush(f"gauge:{name}:t", timestamp)
                pipe.ltrim(f"gauge:{name}:val", 0, BUFFERLEN-1)
                pipe.ltrim(f"gauge:{name}:t", 0, BUFFERLEN-1)
                logger.info(f"Queued push to gauge:{name}:*")
            pipe.execute()
            logger.info(f"Push to gauge:{name}:* executed.")

    japc.subscribeParam(f"{CRIO_HV}/PSU_all_values#I_read", broker_psus)
    logger.info(f"Subscribed to {CRIO_HV}/PSU_all_values#I_read")

    japc.subscribeParam(f"{CRIO_GUN}/PSU_all_values#I_read", broker_psus)
    logger.info(f"Subscribed to {CRIO_GUN}/PSU_all_values#I_read")

    japc.subscribeParam(f"{CRIO_HV}/Gauge_Levels", broker_gauges)
    logger.info(f"Subscribed to {CRIO_HV}/Gauge_Levels")

    japc.startSubscriptions()
    logger.info("Subscriptions started.")

    while True:
        input()


def mock():
    import random
    import time
    logger = start_logger()

    rcl = redis.Redis(host='redis')
    rcl.flushall()
    logger.info("Redis connection opened.")

    val = {}
    while True:
        for psu in ["psu0", "psu2", "psu3", "psu4", "psu5", "psu6"]:
            val[psu] = val.get(psu, 0) + random.random() - 0.5
            timestamp = datetime.datetime.now(TZ).isoformat()
            with rcl.pipeline(transaction=True) as pipe:
                pipe.lpush(f"{psu}:iread:val", val[psu])
                pipe.ltrim(f"{psu}:iread:val", 0, BUFFERLEN-1)
                pipe.lpush(f"{psu}:iread:t", timestamp)
                pipe.ltrim(f"{psu}:iread:t", 0, BUFFERLEN-1)
                pipe.execute()

            logger.info(f"Pushed to {psu}:iread")

        time.sleep(.8 + 0.4 * random.random())

if __name__ == "__main__":
    main()
