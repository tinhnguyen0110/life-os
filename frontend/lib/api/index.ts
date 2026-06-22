/* Barrel — re-exports the api HTTP core + every domain file. @/lib/api resolves here.
   #138-P3: split from the old 1105-line lib/api.ts (pure move). */
export * from "./_client";
export * from "./projects";
export * from "./finance";
export * from "./market";
export * from "./claude";
export * from "./graveyard";
export * from "./journal";
export * from "./activity";
export * from "./brief";
export * from "./settings";
export * from "./wiki";
export * from "./decision";
export * from "./career";
export * from "./reminders";
export * from "./tracing";
export * from "./dev";
export * from "./mcp";
