---
title: 
- Generation of simulated read sets
---

Generate endogenous reads from our sample genome `volpertinger.fasta`. Store the
generated reads in `volpertinger.fastq` and the true read position information
in `volpertinger.coord`. Specify `--seed` to initialize the random number
generator to a defined state such that the same call yields the same set of
reads. If you don't specify `--seed`, you will generate different reads each
time you call this script. `--name` specifies a prefix for the names the
generated reads get, to identify them in the SAM file once they were mapped.
>>>>>>> Stashed changes

```{.bash}
scripts/uniform data/genome/volpertinger.fasta \
    --seed 1234 \
    --name volpertinger_ \
    --output-fastq data/2/volpertinger.coord data/2/volpertinger.fastq \
    25 20 5
```
```{.output}
```

Repeat the same steps for our simulated contaminant exogenous species genome,
`retli.fasta`. In this example twice as many exogenous reads as endogenous reads
are generated.


```{.bash}
scripts/uniform data/retli/retli_tr.fasta \
    --seed 1235 \
    --name retli_ \
    --output-fastq data/2/retli.coord data/2/retli.fastq \
    50 20 5
```
```{.output}
```


The generated reads have only `FFFF.....` as base quality scores, if you want
more control over the read generation process, see the section "Advanced read
generation". 

