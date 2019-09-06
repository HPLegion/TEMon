import datetime
import logging
import redis
import pyjapc

BUFFERLEN = 7200
PSU_HV = [
    {"name":"gun_platform", "id":0},
    {"name":"anode_dt", "id":1},
    {"name":"inner_barrier", "id":2},
    {"name":"extractor_hv", "id":3},
]

PSU_GUN = [
    {"name":"cathode_heating", "id":0},
    {"name":"wehnelt", "id":1},
    {"name":"anode", "id":2},
    {"name":"suppressor", "id":3},
    {"name":"collector", "id":4},
    {"name":"extractor_gun", "id":5},
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

    def broker_currents(name, values):
        psus = PSU_GUN if "Gun" in name else PSU_HV
        timestamp = datetime.datetime.now().isoformat()
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



    rcl = redis.Redis(host='redis')
    logger.info("Redis connection opened.")

    japc = pyjapc.PyJapc(incaAcceleratorName=None)
    logger.info("PyJAPC initialised.")

    japc.subscribeParam("TwinEBIS_cRIO_HV/PSU_all_values#I_read", broker_currents)
    logger.info("Subscribed to TwinEBIS_cRIO_HV/PSU_all_values#I_read")

    japc.subscribeParam("TwinEBIS_cRIO_Gun/PSU_all_values#I_read", broker_currents)
    logger.info("Subscribed to TwinEBIS_cRIO_Gun/PSU_all_values#I_read")

    japc.startSubscriptions()
    logger.info("Subscriptions started.")


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
            timestamp = datetime.datetime.now().isoformat()
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
