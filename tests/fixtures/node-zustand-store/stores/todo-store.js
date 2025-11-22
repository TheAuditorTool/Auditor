/**
 * Todo Store with Immer Middleware
 * Tests: Immer integration, complex nested updates, filtering, sorting
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { immer } from 'zustand/middleware/immer';

/**
 * Todo Store
 * Tests: Immer for immutable updates, nested state, filtering
 */
const useTodoStore = create(
  devtools(
    immer((set, get) => ({
      // State
      todos: [],
      filter: 'all', // 'all', 'active', 'completed'
      sortBy: 'createdAt', // 'createdAt', 'priority', 'dueDate'
      searchQuery: '',

      /**
       * Add todo
       * Tests: Immer state push
       * TAINT FLOW: todoData (user input) -> todos array
       */
      addTodo: (todoData) => {
        set((state) => {
          state.todos.push({
            id: Date.now().toString(),
            title: todoData.title,
            description: todoData.description || '',
            completed: false,
            priority: todoData.priority || 'medium',
            tags: todoData.tags || [],
            dueDate: todoData.dueDate || null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            subtasks: []
          });
        });
      },

      /**
       * Update todo
       * Tests: Immer nested object update
       */
      updateTodo: (todoId, updates) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            Object.assign(todo, updates);
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      /**
       * Toggle todo completion
       * Tests: Immer boolean toggle
       */
      toggleTodo: (todoId) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            todo.completed = !todo.completed;
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      /**
       * Delete todo
       * Tests: Immer array filter
       */
      deleteTodo: (todoId) => {
        set((state) => {
          const index = state.todos.findIndex((t) => t.id === todoId);

          if (index !== -1) {
            state.todos.splice(index, 1);
          }
        });
      },

      /**
       * Add subtask to todo
       * Tests: Immer nested array push
       */
      addSubtask: (todoId, subtaskTitle) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            todo.subtasks.push({
              id: `${todoId}-${Date.now()}`,
              title: subtaskTitle,
              completed: false
            });
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      /**
       * Toggle subtask completion
       * Tests: Immer deeply nested update
       */
      toggleSubtask: (todoId, subtaskId) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            const subtask = todo.subtasks.find((s) => s.id === subtaskId);

            if (subtask) {
              subtask.completed = !subtask.completed;
              todo.updatedAt = new Date().toISOString();
            }
          }
        });
      },

      /**
       * Add tag to todo
       * Tests: Immer array manipulation
       */
      addTag: (todoId, tag) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo && !todo.tags.includes(tag)) {
            todo.tags.push(tag);
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      /**
       * Remove tag from todo
       * Tests: Immer nested array filter
       */
      removeTag: (todoId, tag) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            const index = todo.tags.indexOf(tag);

            if (index !== -1) {
              todo.tags.splice(index, 1);
              todo.updatedAt = new Date().toISOString();
            }
          }
        });
      },

      /**
       * Set filter
       * Tests: Simple state update
       */
      setFilter: (filter) => {
        set({ filter });
      },

      /**
       * Set sort order
       * Tests: Simple state update
       */
      setSortBy: (sortBy) => {
        set({ sortBy });
      },

      /**
       * Set search query
       * Tests: Search state update
       */
      setSearchQuery: (query) => {
        set({ searchQuery: query });
      },

      /**
       * Get filtered todos
       * Tests: Complex filtering logic
       */
      getFilteredTodos: () => {
        const { todos, filter, sortBy, searchQuery } = get();

        // Apply filter
        let filtered = todos;

        if (filter === 'active') {
          filtered = todos.filter((t) => !t.completed);
        } else if (filter === 'completed') {
          filtered = todos.filter((t) => t.completed);
        }

        // Apply search
        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          filtered = filtered.filter(
            (t) =>
              t.title.toLowerCase().includes(query) ||
              t.description.toLowerCase().includes(query) ||
              t.tags.some((tag) => tag.toLowerCase().includes(query))
          );
        }

        // Apply sort
        const sorted = [...filtered].sort((a, b) => {
          if (sortBy === 'priority') {
            const priorityOrder = { high: 0, medium: 1, low: 2 };
            return priorityOrder[a.priority] - priorityOrder[b.priority];
          } else if (sortBy === 'dueDate') {
            if (!a.dueDate) return 1;
            if (!b.dueDate) return -1;
            return new Date(a.dueDate) - new Date(b.dueDate);
          } else {
            // Default: createdAt
            return new Date(b.createdAt) - new Date(a.createdAt);
          }
        });

        return sorted;
      },

      /**
       * Get todos by tag
       * Tests: Tag filtering
       */
      getTodosByTag: (tag) => {
        const { todos } = get();
        return todos.filter((t) => t.tags.includes(tag));
      },

      /**
       * Get overdue todos
       * Tests: Date comparison
       */
      getOverdueTodos: () => {
        const { todos } = get();
        const now = new Date();

        return todos.filter((t) => {
          if (!t.dueDate || t.completed) return false;
          return new Date(t.dueDate) < now;
        });
      },

      /**
       * Get todo statistics
       * Tests: Complex aggregation
       */
      getStatistics: () => {
        const { todos } = get();

        return {
          total: todos.length,
          completed: todos.filter((t) => t.completed).length,
          active: todos.filter((t) => !t.completed).length,
          overdue: get().getOverdueTodos().length,
          byPriority: {
            high: todos.filter((t) => t.priority === 'high').length,
            medium: todos.filter((t) => t.priority === 'medium').length,
            low: todos.filter((t) => t.priority === 'low').length
          }
        };
      },

      /**
       * Clear completed todos
       * Tests: Immer array filter with condition
       */
      clearCompleted: () => {
        set((state) => {
          state.todos = state.todos.filter((t) => !t.completed);
        });
      },

      /**
       * Toggle all todos
       * Tests: Immer bulk update
       */
      toggleAll: () => {
        const allCompleted = get().todos.every((t) => t.completed);

        set((state) => {
          state.todos.forEach((todo) => {
            todo.completed = !allCompleted;
            todo.updatedAt = new Date().toISOString();
          });
        });
      },

      /**
       * Reorder todos
       * Tests: Immer array reordering
       */
      reorderTodos: (fromIndex, toIndex) => {
        set((state) => {
          const [removed] = state.todos.splice(fromIndex, 1);
          state.todos.splice(toIndex, 0, removed);
        });
      }
    })),
    {
      name: 'TodoStore',
      enabled: process.env.NODE_ENV === 'development'
    }
  )
);

/**
 * Selectors
 * Tests: Selector patterns for todo state
 */

export const selectTodos = (state) => state.todos;
export const selectFilteredTodos = (state) => state.getFilteredTodos();
export const selectFilter = (state) => state.filter;
export const selectSortBy = (state) => state.sortBy;
export const selectSearchQuery = (state) => state.searchQuery;
export const selectStatistics = (state) => state.getStatistics();
export const selectOverdueTodos = (state) => state.getOverdueTodos();

// Find specific todo
export const selectTodoById = (todoId) => (state) =>
  state.todos.find((t) => t.id === todoId);

// Get todos by priority
export const selectTodosByPriority = (priority) => (state) =>
  state.todos.filter((t) => t.priority === priority);

export default useTodoStore;
