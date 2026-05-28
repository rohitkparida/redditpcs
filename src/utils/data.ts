import gpus from '../data/gpus.json';
import cpus from '../data/cpus.json';
import motherboards from '../data/motherboards.json';
import ram from '../data/ram.json';
import psus from '../data/psus.json';
import ssds from '../data/ssds.json';
import coolers from '../data/coolers.json';
import cases from '../data/cases.json';

// Individual hardware categories
export { gpus, cpus, motherboards, ram, psus, ssds, coolers, cases };

// Combined hardware categories registry
export const categories = [gpus, cpus, motherboards, ram, ssds, psus, coolers, cases];
