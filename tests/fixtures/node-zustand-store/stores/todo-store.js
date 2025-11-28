import { create } from "zustand";
import { devtools } from "zustand/middleware";
import { immer } from "zustand/middleware/immer";

const useTodoStore = create(
  devtools(
    immer((set, get) => ({
      todos: [],
      filter: "all",
      sortBy: "createdAt",
      searchQuery: "",

      addTodo: (todoData) => {
        set((state) => {
          state.todos.push({
            id: Date.now().toString(),
            title: todoData.title,
            description: todoData.description || "",
            completed: false,
            priority: todoData.priority || "medium",
            tags: todoData.tags || [],
            dueDate: todoData.dueDate || null,
            createdAt: new Date().toISOString(),
            updatedAt: new Date().toISOString(),
            subtasks: [],
          });
        });
      },

      updateTodo: (todoId, updates) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            Object.assign(todo, updates);
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      toggleTodo: (todoId) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            todo.completed = !todo.completed;
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

      deleteTodo: (todoId) => {
        set((state) => {
          const index = state.todos.findIndex((t) => t.id === todoId);

          if (index !== -1) {
            state.todos.splice(index, 1);
          }
        });
      },

      addSubtask: (todoId, subtaskTitle) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo) {
            todo.subtasks.push({
              id: `${todoId}-${Date.now()}`,
              title: subtaskTitle,
              completed: false,
            });
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

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

      addTag: (todoId, tag) => {
        set((state) => {
          const todo = state.todos.find((t) => t.id === todoId);

          if (todo && !todo.tags.includes(tag)) {
            todo.tags.push(tag);
            todo.updatedAt = new Date().toISOString();
          }
        });
      },

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

      setFilter: (filter) => {
        set({ filter });
      },

      setSortBy: (sortBy) => {
        set({ sortBy });
      },

      setSearchQuery: (query) => {
        set({ searchQuery: query });
      },

      getFilteredTodos: () => {
        const { todos, filter, sortBy, searchQuery } = get();

        let filtered = todos;

        if (filter === "active") {
          filtered = todos.filter((t) => !t.completed);
        } else if (filter === "completed") {
          filtered = todos.filter((t) => t.completed);
        }

        if (searchQuery) {
          const query = searchQuery.toLowerCase();
          filtered = filtered.filter(
            (t) =>
              t.title.toLowerCase().includes(query) ||
              t.description.toLowerCase().includes(query) ||
              t.tags.some((tag) => tag.toLowerCase().includes(query)),
          );
        }

        const sorted = [...filtered].sort((a, b) => {
          if (sortBy === "priority") {
            const priorityOrder = { high: 0, medium: 1, low: 2 };
            return priorityOrder[a.priority] - priorityOrder[b.priority];
          } else if (sortBy === "dueDate") {
            if (!a.dueDate) return 1;
            if (!b.dueDate) return -1;
            return new Date(a.dueDate) - new Date(b.dueDate);
          } else {
            return new Date(b.createdAt) - new Date(a.createdAt);
          }
        });

        return sorted;
      },

      getTodosByTag: (tag) => {
        const { todos } = get();
        return todos.filter((t) => t.tags.includes(tag));
      },

      getOverdueTodos: () => {
        const { todos } = get();
        const now = new Date();

        return todos.filter((t) => {
          if (!t.dueDate || t.completed) return false;
          return new Date(t.dueDate) < now;
        });
      },

      getStatistics: () => {
        const { todos } = get();

        return {
          total: todos.length,
          completed: todos.filter((t) => t.completed).length,
          active: todos.filter((t) => !t.completed).length,
          overdue: get().getOverdueTodos().length,
          byPriority: {
            high: todos.filter((t) => t.priority === "high").length,
            medium: todos.filter((t) => t.priority === "medium").length,
            low: todos.filter((t) => t.priority === "low").length,
          },
        };
      },

      clearCompleted: () => {
        set((state) => {
          state.todos = state.todos.filter((t) => !t.completed);
        });
      },

      toggleAll: () => {
        const allCompleted = get().todos.every((t) => t.completed);

        set((state) => {
          state.todos.forEach((todo) => {
            todo.completed = !allCompleted;
            todo.updatedAt = new Date().toISOString();
          });
        });
      },

      reorderTodos: (fromIndex, toIndex) => {
        set((state) => {
          const [removed] = state.todos.splice(fromIndex, 1);
          state.todos.splice(toIndex, 0, removed);
        });
      },
    })),
    {
      name: "TodoStore",
      enabled: process.env.NODE_ENV === "development",
    },
  ),
);

export const selectTodos = (state) => state.todos;
export const selectFilteredTodos = (state) => state.getFilteredTodos();
export const selectFilter = (state) => state.filter;
export const selectSortBy = (state) => state.sortBy;
export const selectSearchQuery = (state) => state.searchQuery;
export const selectStatistics = (state) => state.getStatistics();
export const selectOverdueTodos = (state) => state.getOverdueTodos();

export const selectTodoById = (todoId) => (state) =>
  state.todos.find((t) => t.id === todoId);

export const selectTodosByPriority = (priority) => (state) =>
  state.todos.filter((t) => t.priority === priority);

export default useTodoStore;
