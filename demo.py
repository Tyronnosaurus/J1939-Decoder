"""
Taken from https://stackoverflow.com/questions/66630991/create-mf4-to-be-decode-by-j1939-dbc-asammdf
Creates a dummy MDF in such a way that asammdf can load it.
And more importantly: asammdf shows the Bus Logging tab so that we can decode the data with a DBC dictionary.
I have used this demo as a base for the PrepareMF4.py scripts.
"""

from asammdf import MDF, SUPPORTED_VERSIONS, Signal
import numpy as np
from asammdf.blocks.source_utils import Source

sigs = []
mdf = MDF()


samples = [
    np.array([1,1,1,1,1], dtype=np.uint32),     # BusChannel
    np.array([217056256,217056256,217056256,217056256,217056256], dtype=np.uint32), # ID
    np.array([1,1,1,1,1], dtype=np.uint32),     # IDE
    np.array([1,1,1,1,1], dtype=np.uint32),     # DLC
    np.array([2,2,2,2,2], dtype=np.uint32),     # DataLength
    
    #np.array([111,111,111,111,111], dtype=np.dtype('(8,)u1')),   # DataBytes: array (length 8) of u1
    np.array([0x6F11,0x6F11,0x6F1111,0x6F11,0x6F11], dtype=np.dtype('(8,)u1')),   # DataBytes: array (length 8) of u1

    np.array([1,1,1,1,1], dtype=np.uint32),     # Dir
    np.array([1,1,1,1,1], dtype=np.uint32),     # EDL
    np.array([1,1,1,1,1], dtype=np.uint32)      # BRS
]

print(samples[5])

types = [('CAN_DataFrame.BusChannel', 'u1'),
        ('CAN_DataFrame.ID', '<u4'),
        ('CAN_DataFrame.IDE', 'u1'),
        ('CAN_DataFrame.DLC', 'u1'),
        ('CAN_DataFrame.DataLength', 'u1'),
        ('CAN_DataFrame.DataBytes', 'u1', (8,)),    # 1D array of 8 items. Items are 1byte uint
        ('CAN_DataFrame.Dir', 'u1'),
        ('CAN_DataFrame.EDL', 'u1'),
        ('CAN_DataFrame.BRS', 'u1')
        ]

# Timestamps: evenly spaced values within interval. Default start is 0. Stop not included. Default step is 1.
t = np.arange(stop=5, dtype=np.float64) # 0, 1, 2, 3, 4

sig = Signal(
    samples = np.core.records.fromarrays(arrayList=samples, dtype=np.dtype(types)),
    timestamps = t+10,
    name='Channel_structure_composition',
    comment='Structure channel composition',
    source=Source(
        source_type = Source.SOURCE_BUS,
        bus_type    = Source.BUS_TYPE_CAN,
        name        = "CAN bus",
        path        = "CAN bus",
        comment     = "",
    )
)
sigs.append(sig)

mdf.append(sigs, comment='arrays', common_timebase=True)

mdf.save('Converted/demo.mf4', overwrite=True)
print('finished')