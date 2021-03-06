#!/usr/bin/env python

# @autor Moritz Lell
# @date 2015-Aug-25

import sys
import os.path
from docopt import docopt
import fasta_substring as f
import random as rnd
import tempfile as tmpf
import contextlib
import io
import subprocess as sp
import argparse
import math

# Set this to True to print stack trace on error
debug = True

description = """Samples reads from the specified (multi-FASTA) file MFASTA. 
Read positions will be from random FASTA records of the file and 
will be uniformly distributed. 

Read lengths will be exponentially distributed, with the minimum read
length being N. L influences the number of generated reads which are
:q

reads will be N+L bases or longer, one quarter of the reads
will be N+2L bases or longer; in general: A fraction of
2^(-n) of the reads will be N+(n*L) bases or longer.

If the randomly generated read length exceeds the length of the
input sequence, the whole input sequence is printed.

The MFASTA file needs to be indexed using samtools: 
`samtools faidx MFASTA`
"""

def parse_arguments():

    p = argparse.ArgumentParser(description=description,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('MFASTA', help="A (multi-) FASTA file")
    p.add_argument('N', help="Number of reads to generate")
    p.add_argument('L', help="Minimum read length")
    p.add_argument('S', help="""Decay length: 2^-n of the reads are
                             S*n bases longer than L""")
    p.add_argument('--seed', help=
                           """Seed to initialize the random
                           number generator; same seed leads to same
                           read mapping positions""")
    p.add_argument('--index', nargs=1, help=
            "Specify an alternative location for the FASTA index.")
    p.add_argument('--quiet', action='store_true', help=
            "Don't print a status line")
    p.add_argument('--name', nargs=1, metavar=('PREFIX',), help=
            """Create a read name column called 'name'. Generate a name
            `PREFIX_i` for every read, where i is a counting number""")
    p.add_argument('--output-fastq', nargs=2, metavar=('COORD','FASTQ'), help=
            """Create a FASTQ file from the output. The quality score
            is all F and the read names are specified by `--name`.""")
    p.add_argument('--output', nargs=2, metavar=('COORD','NUCL'), help=
            """ Don't output on standard output, create instead two
            files, named like given in COORD and NUCL. In the file
            COORD all read position information will be written,
            in NUCL the raw sampled nucleotides will be
            written.""")

    a = p.parse_args()

    if a.output_fastq and a.output:
        raise ValueError(
        '--output-fastq and --output cannot be specified both')

    if a.output_fastq and not a.name:
        raise ValueError(
        '--name must be specified if --output-fastq is specified')


    return a



def main(argv): 
    args = parse_arguments()

    mfasta = args.MFASTA
    nreads = int(args.N)
    rlen_min = int(args.L)
    rlen_decay = int(args.S)
    seed = args.seed
    quiet = args.quiet
    name = args.name[0] if args.name else None
    coord_output_file = None
    nucl_output_file  = None
    fastq_output_file = None
    # Set only if --output flag is used
    if args.output:
        coord_output_file = args.output[0] 
        nucl_output_file = args.output[1] 
    # Set only if --output-fastq flag is used
    if args.output_fastq:
        coord_output_file = args.output_fastq[0] 
        fastq_output_file = args.output_fastq[1]
    
    index_name = args.index
    if not index_name: index_name = mfasta+".fai"

    if not os.path.isfile(index_name):
        raise Exception("Index file (*.fai) not found. Execute "+
        "'samtools faidx' on the FASTA file first or use the "+
        "--index parameter if the index file has a non-standard name.")

    # Read in the information from the .fai file
    with open(index_name,"rt") as index_fd:
        index = f.FastaIndex(index_fd)

    # Construct main pipe. 
    header = ['record','start','end','read']
    pipe = read_sampler(mfasta, index, nreads, rlen_min, rlen_decay,
            seed)
    if name:
        pipe = name_adder(pipe, name)
        header = ['name'] + header
    if not quiet: 
        pipe = status_updater(pipe, num_elem=nreads)

    outfields = len(header)
    # If --output is set, split the output in two files
    if nucl_output_file:
        with open(coord_output_file,'wt') as coord_fd, \
             open(nucl_output_file,'wt') as nucl_fd:

            print("\t".join(header[0:outfields-1]),file=coord_fd)

            column_splitter(
                col_ranges=[list(range(0,outfields-1)),[outfields-1]],
                files = [coord_fd, nucl_fd],
                table = pipe
            )
    elif fastq_output_file:
        from synth_fastq import print_fastq_lines
        with open(coord_output_file,'wt') as coord_fd , \
             open(fastq_output_file,'wt') as fastq_fd:
            nucl_stringio = io.StringIO()

            print("\t".join(header[0:outfields-1]),file=coord_fd)

            column_splitter(
                col_ranges=[list(range(0,outfields-1)),[outfields-1]],
                files = [coord_fd, nucl_stringio],
                table = pipe
            )

            nucl = nucl_stringio.getvalue().splitlines()
            qual = constantQualityStrings(nucl)
            print_fastq_lines\
                    ( iter(nucl)
                    , qual
                    , name_generator(name)
                    , fastq_fd)

    # If --output is not set -> printed all to stdout
    else:
        print("\t".join(header),file=sys.stdout)
        column_splitter(
            table = pipe 
        ) 

def name_generator(prefix):
    i = 1
    while True:
        yield prefix+str(i)
        i += 1

def name_adder(table, prefix):
    """Prefix each tuple with a name `prefix_i`, where i is a counting
    number"""
    names = name_generator(prefix)
    for row,name in zip(table,names):
        yield (name,) + row


def column_splitter(table, col_ranges=None, files=[sys.stdout]):
    """table is expected to be a list of lists (or other iterables).
    Lists of lists can be thought of forming a table, therefore 
    a column is here an element at the same position throughout
    subsequent elements of table.
    The specified columns are written to the specified files, one line 
    per element of `table`. If col_ranges == None, all columns are 
    written to the first file. Example: 
    If 
        table = [(1,2,3),(4,5,6)], 
        col_ranges = [[1,2],[3]] and 
        files == ['fileA', 'fileB'], 
    then to the files is written as follows:
        fileA << "1→2<>4→5<>"
        fileB << "3<>6<>"
    where → == tab character and <> == newline character"""
    
    for row in table:
        if not col_ranges:
            # All columns
            col_ranges = [[x for x in range(0,len(row))]]

        for file,col_range in zip(files, col_ranges):
            values_to_print = [str(row[i]) for i in col_range]
            print("\t".join(values_to_print), file=file)



def status_updater(iterable, num_elem, stream=sys.stderr, line_width=80):
    """Forward every element of iterable and update a status line in the
    course"""

    n_done = 0
    steps = max(num_elem // line_width,1)
    statusLine(line_width,n_done,num_elem)

    for element in iterable:
        n_done += 1
        if n_done % steps == 0 or n_done == num_elem: 
            statusLine(line_width,n_done,num_elem)

        yield element
    # New line after status line is complete
    print("",file=stream)


def read_sampler(mfasta, index, nreads, rlen_min, rlen_decay,
        seed=None):
    """ Using file mfasta, FastaIndex object index, generate a count
    of nreads reads sampled from mfasta. Minimum length: rlen_min,
    with longer reads becoming exponentially more unlikely, with a
    decay constant of rlen_decay. """

    if seed:
        rnd.seed(seed)

    with open(mfasta,"rt") as fd:

        # Get list of record names
        recordnames = list(sorted(index.entries.keys()))

        # Extract sequences out of the MFASTA file at random
        for i in range(0,nreads):

            # Randomly choose record
            record = rnd.choice(recordnames)
            indexEntry = index.entries[record]
            len_record = indexEntry.length_char

            # Randomly choose sequence length 
            # But never generate 0
            rlen = int(rnd.expovariate(math.log(2)/rlen_decay))+rlen_min
            if rlen > len_record:
                rlen = len_record
            # Random beginning position uniformly sampled from
            #    [1 .. (record length - read length)]
            # the value of the argument is never reached
            # i.e randrange(1) returns values of range {0}
            #     randrange(2) returns values of range {0,1}
            start = rnd.randrange(1,len_record-rlen+2)
            # Calculate end of region to extract, length is inclusive
            # start = 1, len = 1 => end base = 1
            # start = 1, len = 2 => end base = 2 ...
            end = start + rlen - 1

            read = f.slice(fd, index, record, start-1, rlen)

            yield (record, start, end, read)


def constantQualityStrings(iterable):
    for f in iterable:
        yield "F"*len(f)


def statusMsg(msg,**kwargs):
    """ Print a status message """
    print(msg,file=sys.stderr,**kwargs)

def statusLine(width, now, end=100):
    """ Print a status line. Repeated calling updates the line."""
    msg = "{}/{}".format(now,end)
    barwidth = width - len(msg) - 3 # 2: [ and ], 1 space
    ratio = now / end
    nfull = round(ratio * barwidth)
    nempty = barwidth - nfull
    sys.stderr.write("["+("="*nfull)+(" "*nempty)+"] "+msg)
    sys.stderr.write("\r"*width)
    sys.stderr.flush()



if __name__ == "__main__": 
    try:
        main(sys.argv)
    except Exception as e:
        if debug: raise
        print('Error: ',end='',file=sys.stderr)
        print(e, file=sys.stderr)
        sys.exit(1)



# vim: tw=70


