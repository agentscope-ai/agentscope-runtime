import {
  IAgentScopeRuntimeWebUISession,
  IAgentScopeRuntimeWebUISessionAPI,
} from '@agentscope-ai/chat';

class SessionApi implements IAgentScopeRuntimeWebUISessionAPI {
  private lsKey: string;
  private sessionList: IAgentScopeRuntimeWebUISession[];

  constructor() {
    this.lsKey = 'agent-scope-runtime-webui-sessions';
    this.sessionList = [];
  }

  async getSessionList() {
    this.sessionList = JSON.parse(localStorage.getItem(this.lsKey) || '[]');
    return [...this.sessionList];
  }

  async getSession(sessionId: string) {
    return this.sessionList.find((session) => session.id === sessionId) as IAgentScopeRuntimeWebUISession;
  }

  async updateSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    const index = this.sessionList.findIndex((item) => item.id === session.id);
    if (index > -1) {
      this.sessionList[index] = {
        ...this.sessionList[index],
        ...session,
      };
      localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList));
    }

    return [...this.sessionList];
  }

  async createSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    session.id = Date.now().toString();
    this.sessionList.unshift(session as IAgentScopeRuntimeWebUISession);
    localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList));
    return [...this.sessionList];
  }

  async removeSession(session: Partial<IAgentScopeRuntimeWebUISession>) {
    this.sessionList = this.sessionList.filter(
      (item) => item.id !== session.id,
    );
    localStorage.setItem(this.lsKey, JSON.stringify(this.sessionList));
    return [...this.sessionList];
  }
}

export default new SessionApi();
