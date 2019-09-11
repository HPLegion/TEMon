import datetime
import logging
import redis
import pytz
import pyjapc

TZ = pytz.timezone('Europe/Zurich')
BUFFERLEN = 7200
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


    def broker_currents(name, values):
        psus = PSU_GUN if "Gun" in name else PSU_HV
        timestamp = datetime.datetime.now(TZ).isoformat()
        with rcl.pipeline(transaction=True) as pipe:
            for psu in psus:
                name = psu["name"]
                val = values[psu["id"]]
                pipe.lpush(f"{name}:iread:val", val)
                pipe.lpush(f"{name}:iread:t", timestamp)
                pipe.ltrim(f"{name}:iread:val", 0, BUFFERLEN-1)
                pipe.ltrim(f"{name}:iread:t", 0, BUFFERLEN-1)
                logger.info(f"Queued push to {name}:iread")
            pipe.execute()
            logger.info(f"Push executed.")

    japc.subscribeParam("TwinEBIS_cRIO_HV/PSU_all_values#I_read", broker_currents)
    logger.info("Subscribed to TwinEBIS_cRIO_HV/PSU_all_values#I_read")

    japc.subscribeParam("TwinEBIS_cRIO_Gun/PSU_all_values#I_read", broker_currents)
    logger.info("Subscribed to TwinEBIS_cRIO_Gun/PSU_all_values#I_read")

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
