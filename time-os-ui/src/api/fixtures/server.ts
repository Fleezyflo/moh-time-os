/**
 * MSW Server Setup for Node.js (tests).
 */

import { setupServer } from 'msw/node';
import { handlers } from './handlers';

export const server = setupServer(...handlers);

export default server;
