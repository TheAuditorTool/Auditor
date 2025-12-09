/**
 * Elasticsearch adapter - HOP 10: Search engine integration.
 *
 * Performs searches with NoSQL injection vulnerability.
 */

export class ElasticsearchAdapter {
  /**
   * Search with filter.
   *
   * HOP 10: NoSQL INJECTION SINK - user-controlled filter.
   *
   * @param filter - TAINTED filter object
   */
  search(filter: any): any {
    // VULNERABLE: User-controlled filter passed directly to query DSL
    // NoSQL injection via $where, $regex, etc.
    const query = {
      query: {
        bool: {
          must: filter, // TAINTED - NoSQL Injection
        },
      },
    };

    // Simulated Elasticsearch query execution
    console.log('Executing ES query:', JSON.stringify(query));
    return { hits: [], query };
  }

  /**
   * Index document.
   *
   * @param index - Index name
   * @param doc - TAINTED document
   */
  index(indexName: string, doc: any): any {
    // TAINTED document indexed
    return { indexed: true, index: indexName };
  }

  /**
   * Raw query (very dangerous).
   *
   * @param queryDsl - TAINTED query DSL
   */
  rawQuery(queryDsl: any): any {
    // VULNERABLE: Direct execution of user-provided query
    return { results: [], query: queryDsl };
  }
}
