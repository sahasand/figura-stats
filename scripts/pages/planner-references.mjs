// Generate the native-R browser-parity fixtures from the same displayed defaults.
import { METHODS, defaultsFor } from '../../web/sample-size/catalog.js';
import { spawnSync } from 'node:child_process';
import {writeFile} from 'node:fs/promises';
const specs=METHODS.map(m=>({name:m.title,spec:defaultsFor(m.id)}));
const result=spawnSync('Rscript',['-e',`source('R/sample-size.R'); input <- paste(readLines(file('stdin'), warn=FALSE), collapse='\\n'); plans <- jsonlite::fromJSON(input, simplifyVector=FALSE); out <- lapply(plans, function(s) {s$result <- sample_size_plan(s$spec); s}); cat(jsonlite::toJSON(out, auto_unbox=TRUE, digits=12, null='null', pretty=TRUE))`],{input:JSON.stringify(specs),encoding:'utf8'});
if(result.status!==0) throw new Error(result.stderr);
await writeFile('tests/fixtures/sample-size-reference.json',result.stdout+'\n');
